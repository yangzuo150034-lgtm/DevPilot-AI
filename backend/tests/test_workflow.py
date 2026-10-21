import io
import zipfile

import pytest

from app.schemas import TaskRequest
from app.service import Service


def new_task(service, variant="D"):
    repo = service.import_repository("demo://calculator")
    task = service.create_task(
        TaskRequest(
            repository_id=repo["id"],
            variant=variant,
            prompt="Fix add so it returns the sum of two numbers",
        )
    )
    return repo, task


@pytest.mark.parametrize("variant", ["A", "B", "C", "D"])
def test_workflow_waits_for_exact_approval(service, variant):
    repo, task = new_task(service, variant)
    service.execute(task["id"])
    waiting = service.task(task["id"])
    assert waiting["status"] == "awaiting_approval", waiting
    assert "return a - b" in service.repository(repo["id"]).files["calculator.py"]
    with pytest.raises(ValueError, match="digest"):
        service.decide(task["id"], {"approved": True, "patch_digest": "0" * 64})
    with pytest.raises(ValueError, match="approved"):
        service.export(task["id"])
    service.decide(
        task["id"], {"approved": True, "patch_digest": waiting["result"]["patch"]["digest"]}
    )
    service.execute(task["id"])
    done = service.task(task["id"])
    assert done["status"] == "approved_unverified", done
    assert done["result"]["test_result"]["status"] == "not_run"
    assert done["result"]["usage"]["model_calls"] == 0
    bundle = zipfile.ZipFile(io.BytesIO(service.export(task["id"])))
    assert b"return a + b" in bundle.read("source/calculator.py")
    assert "return a - b" in service.repository(repo["id"]).files["calculator.py"]


def test_checkpoint_survives_process_restart(settings):
    first = Service(settings)
    _, task = new_task(first)
    first.execute(task["id"])
    patch_digest = first.task(task["id"])["result"]["patch"]["digest"]
    first.close()
    second = Service(settings)
    try:
        second.decide(task["id"], {"approved": False, "patch_digest": patch_digest})
        second.execute(task["id"])
        assert second.task(task["id"])["status"] == "rejected"
        with pytest.raises(ValueError):
            second.export(task["id"])
    finally:
        second.close()


def test_duplicate_execution_is_noop(service):
    _, task = new_task(service)
    service.execute(task["id"])
    events = service.task(task["id"])["events"]
    service.execute(task["id"])
    assert service.task(task["id"])["events"] == events


def test_repository_import_idempotent(service):
    assert (
        service.import_repository("demo://calculator")["id"]
        == service.import_repository("demo://calculator")["id"]
    )


def test_missing_model_key_fails_before_task_creation(service):
    repo = service.import_repository("demo://calculator")
    with pytest.raises(ValueError, match="API_KEY"):
        service.create_task(
            TaskRequest(repository_id=repo["id"], provider="openai", prompt="Fix calculator add")
        )
