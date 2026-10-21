from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now() -> str:
    return datetime.now(UTC).isoformat()


def identifier() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(400))
    commit: Mapped[str] = mapped_column(String(64))
    files: Mapped[dict] = mapped_column(JSON)
    chunks: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    repository_id: Mapped[str] = mapped_column(String(32), index=True)
    prompt: Mapped[str] = mapped_column(String(4000))
    provider: Mapped[str] = mapped_column(String(20))
    variant: Mapped[str] = mapped_column(String(1))
    retrieval: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    events: Mapped[list] = mapped_column(JSON, default=list)
    decision: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


def database(url: str):
    args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=args, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def repository_view(repo: Repository, include_files: bool = False) -> dict:
    data = {
        key: getattr(repo, key) for key in ["id", "name", "url", "commit", "stats", "created_at"]
    }
    data["paths"] = sorted(repo.files)
    if include_files:
        data["files"] = repo.files
    return data


def task_view(task: Task) -> dict:
    return {
        key: getattr(task, key)
        for key in [
            "id",
            "repository_id",
            "prompt",
            "provider",
            "variant",
            "retrieval",
            "status",
            "result",
            "events",
            "created_at",
            "updated_at",
        ]
    }
