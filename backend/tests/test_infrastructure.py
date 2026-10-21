import os

import pytest

from app.schemas import TaskRequest
from app.service import Service

pytestmark = pytest.mark.skipif(
    os.getenv("DEVPILOT_TEST_INFRASTRUCTURE") != "1",
    reason="Requires PostgreSQL, Redis and Qdrant integration services",
)


def test_postgres_checkpoint_rq_and_remote_qdrant(settings):
    from redis import Redis
    from rq import Queue, SimpleWorker

    settings.database_url = "postgresql+psycopg://devpilot:ci_only_password@127.0.0.1:5432/devpilot"
    settings.checkpoint_url = "postgresql://devpilot:ci_only_password@127.0.0.1:5432/devpilot"
    settings.qdrant_url = "http://127.0.0.1:6333"
    service = Service(settings)
    try:
        repo = service.import_repository("demo://calculator")
        assert service.retrieve(repo["id"], "add sum return", "hybrid")
        connection = Redis.from_url("redis://127.0.0.1:6379/0")
        queue = Queue("integration-devpilot", connection=connection)
        job = queue.enqueue("builtins.sum", [1, 2, 3])
        SimpleWorker([queue], connection=connection).work(burst=True)
        assert job.return_value() == 6
        task = service.create_task(
            TaskRequest(repository_id=repo["id"], prompt="Fix the add function")
        )
        service.execute(task["id"])
        assert service.task(task["id"])["status"] == "awaiting_approval"
        service.decide(
            task["id"],
            {
                "approved": False,
                "patch_digest": service.task(task["id"])["result"]["patch"]["digest"],
            },
        )
        service.execute(task["id"])
        assert service.task(task["id"])["status"] == "rejected"
    finally:
        service.close()
