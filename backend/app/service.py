import contextlib
import io
import json
import sqlite3
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import select, update

from app.agents.workflow import build_workflow
from app.core.config import Settings
from app.harness.patches import apply_patch
from app.rag.chunks import chunk_files
from app.rag.search import CodeSearch
from app.repositories import demo_snapshot, import_github
from app.schemas import TaskRequest
from app.storage import Repository, Task, database, now, repository_view, task_view


class Service:
    def __init__(self, settings: Settings):
        settings.prepare()
        self.settings = settings
        self.engine, self.sessions = database(settings.database_url)
        self.search = CodeSearch(settings)
        self.search_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="devpilot")

    def close(self):
        self.executor.shutdown(wait=True)
        self.search.close()
        self.engine.dispose()

    def repositories(self):
        with self.sessions() as session:
            return [
                repository_view(r)
                for r in session.scalars(select(Repository).order_by(Repository.created_at.desc()))
            ]

    def repository(self, repo_id):
        with self.sessions() as session:
            repo = session.get(Repository, repo_id)
            if repo is None:
                raise LookupError("Repository not found")
            session.expunge(repo)
            return repo

    def import_repository(self, url: str):
        snapshot = (
            demo_snapshot() if url == "demo://calculator" else import_github(url, self.settings)
        )
        chunks = chunk_files(snapshot["files"], snapshot["commit"])
        with self.sessions.begin() as session:
            existing = session.scalar(
                select(Repository).where(
                    Repository.url == snapshot["url"],
                    Repository.commit == snapshot["commit"],
                )
            )
            if existing:
                return repository_view(existing)
            snapshot["stats"]["chunks"] = len(chunks)
            snapshot["stats"]["languages"] = sorted(
                {p.rsplit(".", 1)[-1] for p in snapshot["files"]}
            )
            repo = Repository(**snapshot, chunks=chunks)
            session.add(repo)
            session.flush()
            return repository_view(repo)

    def retrieve(self, repo_id, query, mode="hybrid", limit=5):
        repo = self.repository(repo_id)
        with self.search_lock:
            return self.search.search(repo.id, repo.chunks, query, mode, limit)

    def create_task(self, request: TaskRequest):
        repo = self.repository(request.repository_id)
        if request.provider == "demo" and repo.url != "demo://calculator":
            raise ValueError(
                "Demo mode supports only the bundled repository; configure a model for GitHub tasks"
            )
        if request.provider == "openai" and not self.settings.openai_api_key.get_secret_value():
            raise ValueError("Configure DEVPILOT_OPENAI_API_KEY on the server first")
        with self.sessions.begin() as session:
            task = Task(**request.model_dump())
            session.add(task)
            session.flush()
            return task_view(task)

    def tasks(self):
        with self.sessions() as session:
            return [
                task_view(task)
                for task in session.scalars(
                    select(Task).order_by(Task.created_at.desc()).limit(100)
                )
            ]

    def task(self, task_id):
        with self.sessions() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise LookupError("Task not found")
            return task_view(task)

    def event(self, task_id, role, message, details):
        with self.sessions.begin() as session:
            task = session.get(Task, task_id)
            task.events = [
                *task.events[-99:],
                {"at": now(), "role": role, "message": message[:3000], "details": details},
            ]
            task.updated_at = now()

    def schedule(self, task_id):
        if self.settings.execution_backend == "rq":
            from redis import Redis
            from rq import Queue

            Queue("devpilot", connection=Redis.from_url(self.settings.redis_url)).enqueue(
                "app.worker.run_task",
                task_id,
                job_timeout=1200,
                result_ttl=3600,
            )
        else:
            self.executor.submit(self.execute, task_id)

    @contextlib.contextmanager
    def checkpointer(self):
        if self.settings.checkpoint_url:
            from langgraph.checkpoint.postgres import PostgresSaver

            with PostgresSaver.from_conn_string(self.settings.checkpoint_url) as saver:
                saver.setup()
                yield saver
        else:
            with contextlib.closing(
                sqlite3.connect(self.settings.data_dir / "checkpoints.db", check_same_thread=False)
            ) as conn:
                yield SqliteSaver(conn)

    def execute(self, task_id):
        with self.sessions.begin() as session:
            claimed = session.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.status == "queued",
                )
                .values(status="running", updated_at=now())
            )
            if claimed.rowcount != 1:
                return
            task = session.get(Task, task_id)
            session.expunge(task)
        started = time.monotonic()
        state = {}
        try:
            repo = self.repository(task.repository_id)
            with self.checkpointer() as saver:
                graph = build_workflow(
                    self.settings,
                    repo,
                    task,
                    self.search,
                    saver,
                    lambda role, message, details: self.event(task_id, role, message, details),
                )
                config = {"configurable": {"thread_id": task_id}, "recursion_limit": 40}
                previous = graph.get_state(config)
                interrupted = any(getattr(item, "interrupts", ()) for item in previous.tasks)
                if task.decision and interrupted:
                    arg = Command(resume=task.decision)
                elif previous.values:
                    arg = None
                else:
                    arg = {"task_id": task_id, "prompt": task.prompt}
                try:
                    with self.search_lock:
                        graph.invoke(arg, config=config)
                except Exception:
                    state = dict(graph.get_state(config).values)
                    raise
                snapshot = graph.get_state(config)
                state = dict(snapshot.values)
                pending = any(getattr(item, "interrupts", ()) for item in snapshot.tasks)
                status = (
                    "awaiting_approval"
                    if pending
                    else state.get("report", {}).get("status", "failed")
                )
                result = state.get("report", state)
        except Exception as error:
            status = "failed"
            result = {
                **state,
                "error": type(error).__name__,
                "message": (
                    "Execution failed safely. Check configuration or retry; "
                    "no host code was executed."
                ),
            }
            self.event(
                task_id,
                "supervisor",
                "执行失败，可在修正配置后恢复",
                {"category": type(error).__name__},
            )
        with self.sessions.begin() as session:
            current = session.get(Task, task_id)
            current.status = status
            current.result = {**result, "last_run_seconds": round(time.monotonic() - started, 3)}
            current.updated_at = now()

    def decide(self, task_id, decision: dict):
        current = self.task(task_id)
        if current["status"] != "awaiting_approval":
            raise ValueError("Task is not waiting for approval")
        patch = current["result"].get("patch", {})
        if patch.get("digest") != decision["patch_digest"]:
            raise ValueError("Approval digest does not match the current patch")
        with self.sessions.begin() as session:
            changed = session.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.status == "awaiting_approval",
                )
                .values(status="queued", decision=decision, updated_at=now())
            )
            if changed.rowcount != 1:
                raise ValueError("Task was already decided")

    def retry(self, task_id):
        current = self.task(task_id)
        stale = (
            current["status"] == "running"
            and (datetime.now(UTC) - datetime.fromisoformat(current["updated_at"])).total_seconds()
            > 1200
        )
        if current["status"] not in {"failed", "queued"} and not stale:
            raise ValueError(
                "Retry requires a failed/queued task or an expired 20-minute execution lease"
            )
        with self.sessions.begin() as session:
            changed = session.execute(
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.status == current["status"],
                )
                .values(status="queued", updated_at=now())
            )
            if changed.rowcount != 1:
                raise ValueError("Task state changed; refresh before retrying")

    def export(self, task_id):
        task = self.task(task_id)
        result = task["result"]
        if task["status"] not in {
            "completed",
            "approved_unverified",
            "test_failed",
        } or not result.get("approved"):
            raise ValueError("Export requires an approved patch")
        repo = self.repository(task["repository_id"])
        files = apply_patch(repo.files, result["patch"], repo.commit)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path, content in files.items():
                bundle.writestr("source/" + path, content)
            bundle.writestr("patch.diff", result["patch"]["diff"])
            bundle.writestr("report.json", json.dumps(task, ensure_ascii=False, indent=2))
        return output.getvalue()
