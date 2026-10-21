import pytest
from fastapi.testclient import TestClient

from app.core.security import allowed_path, github_repo, safe_path
from app.harness.patches import apply_patch, validate_patch
from app.harness.sandbox import DockerSandbox
from app.main import create_app
from app.repositories import DEMO_FILES


@pytest.mark.parametrize(
    "path", ["../secret.py", "/etc/passwd", "C:/keys.py", "a\\b.py", "a/../b.py", "a//b.py"]
)
def test_path_traversal_rejected(path):
    with pytest.raises(ValueError):
        safe_path(path)


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        ".git/config",
        "config/secrets.json",
        "node_modules/a.js",
        ".ssh/id_rsa",
        "private.key",
        "credentials.json",
    ],
)
def test_sensitive_paths_not_imported(path):
    assert not allowed_path(path)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://evil.com/a/b",
        "https://github.com.evil.com/a/b",
        "https://github.com/a/b/tree/main",
        "https://user:pass@github.com/a/b",
        "https://github.com/a/b?x=y",
        "https://127.0.0.1/a/b",
        "https://github.com/../b",
    ],
)
def test_import_url_allowlist(url):
    with pytest.raises(ValueError):
        github_repo(url)


def test_patch_tampering_is_rejected():
    patch = validate_patch(
        DEMO_FILES,
        {
            "summary": "fix",
            "edits": [
                {"path": "calculator.py", "old": "return a - b", "new": "return a + b"},
            ],
        },
        "commit-a",
    )
    patch["proposal"]["edits"][0]["new"] = "return 0"
    with pytest.raises(ValueError, match="changed"):
        apply_patch(DEMO_FILES, patch, "commit-a")


def test_sandbox_never_falls_back_to_host(settings, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No process should be launched")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    assert DockerSandbox(settings).run(DEMO_FILES)["status"] == "not_run"


def test_sandbox_command_has_isolation(settings, tmp_path):
    command = DockerSandbox(settings).command(tmp_path, "devpilot-test")
    for argument in [
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--pids-limit=64",
        "--security-opt=no-new-privileges:true",
        "--pull=never",
        "--user=65534:65534",
    ]:
        assert argument in command
    assert command[-8:] == ["python", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]


def test_api_auth_and_host_protection(settings):
    settings.api_token = "testing-token"
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/tasks").status_code == 401
        assert (
            client.get(
                "/api/v1/tasks", headers={"Authorization": "Bearer testing-token"}
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/api/v1/tasks",
                headers={"Authorization": "Bearer testing-token", "Host": "attacker.example"},
            ).status_code
            == 400
        )
