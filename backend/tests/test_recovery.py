from app.agents.models import RoleModels
from app.schemas import TaskRequest


def test_failed_node_resumes_without_repeating_completed_plan(service, monkeypatch):
    repo = service.import_repository("demo://calculator")
    task = service.create_task(TaskRequest(repository_id=repo["id"], prompt="Fix the addition bug"))
    original = RoleModels.code

    def fail(*args, **kwargs):
        raise TimeoutError("transient model issue")

    monkeypatch.setattr(RoleModels, "code", fail)
    service.execute(task["id"])
    assert service.task(task["id"])["status"] == "failed"
    monkeypatch.setattr(RoleModels, "code", original)
    service.retry(task["id"])
    service.execute(task["id"])
    resumed = service.task(task["id"])
    assert resumed["status"] == "awaiting_approval"
    assert sum(event["role"] == "planner" for event in resumed["events"]) == 1


def test_policy_blocks_model_patch_to_tests(service, monkeypatch):
    repo = service.import_repository("demo://calculator")
    task = service.create_task(TaskRequest(repository_id=repo["id"], prompt="Fix the addition bug"))
    monkeypatch.setattr(
        RoleModels,
        "code",
        lambda *args: {
            "summary": "Unsafe",
            "edits": [
                {
                    "path": "tests/test_calculator.py",
                    "old": "self.assertEqual(add(2, 3), 5)",
                    "new": "self.assertEqual(add(2, 3), -1)",
                },
            ],
        },
    )
    service.execute(task["id"])
    assert service.task(task["id"])["status"] == "failed"
