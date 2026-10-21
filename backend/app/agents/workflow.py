import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.models import RoleModels
from app.harness.patches import apply_patch, validate_patch
from app.harness.sandbox import DockerSandbox


class TaskState(TypedDict, total=False):
    task_id: str
    prompt: str
    plan: dict
    evidence: list
    proposal: dict
    patch: dict
    review: dict
    approved: bool
    test_result: dict
    report: dict
    usage: dict


def build_workflow(settings, repository, task, search, checkpointer, record):
    models = RoleModels(settings, task.provider, record)
    previous_usage = next(
        (event["details"] for event in reversed(task.events) if event["role"] == "usage"),
        task.result.get("usage", {}),
    )
    models.usage.input_tokens = previous_usage.get("input_tokens", 0)
    models.usage.output_tokens = previous_usage.get("output_tokens", 0)
    models.usage.calls = previous_usage.get("model_calls", 0)
    started = time.monotonic()
    files = repository.files

    def planner(state):
        result = models.plan(state["prompt"])
        record("planner", "任务计划已生成", result)
        return {"plan": result, "usage": models.usage.snapshot()}

    def research(state):
        evidence = search.search(
            repository.id, repository.chunks, state["prompt"], task.retrieval, 8
        )
        record(
            "research",
            f"检索到 {len(evidence)} 个代码片段",
            {
                "citations": [
                    {k: c[k] for k in ["path", "start_line", "end_line", "commit"]}
                    for c in evidence
                ],
            },
        )
        return {"evidence": evidence}

    def coding(state):
        if task.variant == "A":
            evidence = []
            context = "\n".join(f"FILE {p}\n{text}" for p, text in sorted(files.items()))
        else:
            evidence = state.get("evidence", [])
            context = "\n\n".join(
                f"{c['path']}:{c['start_line']}-{c['end_line']}\n{c['text']}" for c in evidence
            )
        context = context[: settings.context_chars]
        proposal = models.code(
            state["prompt"],
            context,
            files,
            task.variant == "D",
            repository.url == "demo://calculator",
        )
        patch = validate_patch(files, proposal, repository.commit)
        record(
            "coding",
            proposal["summary"],
            {"changed_paths": patch["changed_paths"], "patch_digest": patch["digest"]},
        )
        return {"proposal": proposal, "patch": patch, "usage": models.usage.snapshot()}

    def review(state):
        # Enforce policy outside the model, even when model review approves.
        for path in state["patch"]["changed_paths"]:
            if (
                path.startswith(("tests/", ".github/"))
                or "/tests/" in path
                or path.rsplit("/", 1)[-1].startswith("test_")
                or path.endswith((".json", ".toml", ".yaml", ".yml"))
                or path.rsplit("/", 1)[-1] in {"Dockerfile", "requirements.txt", "conftest.py"}
                or ".config." in path.rsplit("/", 1)[-1]
            ):
                raise ValueError("Patch policy blocks test and configuration edits")
        if task.variant in {"A", "B"}:
            result = {
                "approved": True,
                "findings": ["基线模式仅执行确定性策略检查，无独立 Review Agent。"],
            }
        else:
            result = models.review(state["prompt"], state["patch"]["diff"])
        record("review", "审查完成", result)
        return {"review": result, "usage": models.usage.snapshot()}

    def approval(state):
        decision = interrupt(
            {
                "patch_digest": state["patch"]["digest"],
                "commit": repository.commit,
                "summary": state["proposal"]["summary"],
                "diff": state["patch"]["diff"],
            }
        )
        if (
            not isinstance(decision, dict)
            or decision.get("patch_digest") != state["patch"]["digest"]
        ):
            raise ValueError("Approval does not match the reviewed patch")
        record("approval", "人工批准补丁" if decision.get("approved") else "人工拒绝补丁", decision)
        return {"approved": decision.get("approved") is True}

    def testing(state):
        candidate = apply_patch(files, state["patch"], repository.commit)
        sandbox = DockerSandbox(settings)
        baseline = sandbox.run(files)
        result = sandbox.run(candidate)
        result["baseline"] = baseline
        record("sandbox", f"候选补丁测试：{result['status']}", result)
        return {"test_result": result}

    def report(state):
        status = "rejected"
        if state["review"]["approved"] and state.get("approved"):
            outcome = state.get("test_result", {}).get("status")
            status = (
                "completed"
                if outcome == "passed"
                else ("test_failed" if outcome in {"failed", "timeout"} else "approved_unverified")
            )
        result = {
            "status": status,
            "provider": task.provider,
            "variant": task.variant,
            "model": settings.model if task.provider == "openai" else "deterministic-demo-fixture",
            "repository": repository.name,
            "commit": repository.commit,
            "summary": state["proposal"]["summary"],
            "plan": state.get("plan"),
            "evidence": state.get("evidence", []),
            "patch": state["patch"],
            "review": state["review"],
            "approved": state.get("approved", False),
            "test_result": state.get(
                "test_result", {"status": "not_run", "reason": "Patch rejected"}
            ),
            "usage": models.usage.snapshot(),
            "active_run_seconds": round(time.monotonic() - started, 3),
            "note": "演示输出不代表真实模型能力。"
            if task.provider == "demo"
            else "Model output is untrusted. Approval and sandbox checks are independent.",
        }
        record("report", "执行报告已生成", {"status": status})
        return {"report": result}

    graph = StateGraph(TaskState)
    for name, fn in [
        ("plan", planner),
        ("research", research),
        ("code", coding),
        ("review", review),
        ("approval", approval),
        ("test", testing),
        ("report", report),
    ]:
        graph.add_node(name, fn)
    if task.variant in {"C", "D"}:
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "research")
    else:
        graph.add_edge(START, "research" if task.variant == "B" else "code")
    graph.add_edge("research", "code")
    graph.add_edge("code", "review")
    graph.add_conditional_edges(
        "review", lambda s: "approval" if s["review"]["approved"] else "report"
    )
    graph.add_conditional_edges("approval", lambda s: "test" if s["approved"] else "report")
    graph.add_edge("test", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)
