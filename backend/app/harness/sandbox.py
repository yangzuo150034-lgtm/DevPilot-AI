"""Fixed Docker unittest runner. No host execution fallback or model-provided commands."""

import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings
from app.core.security import safe_path


class DockerSandbox:
    def __init__(self, settings: Settings):
        self.settings = settings

    def command(self, directory: Path, name: str) -> list[str]:
        source = str(directory.resolve())
        if self.settings.sandbox_host_dir:
            source = self.settings.sandbox_host_dir.rstrip("/") + "/" + directory.name
        return [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--log-driver=none",
            "--name",
            name,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--pids-limit=64",
            "--memory=256m",
            "--memory-swap=256m",
            "--cpus=1",
            "--user=65534:65534",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=32m",
            "--ulimit",
            "nofile=128:128",
            "--mount",
            f"type=bind,source={source},target=/workspace,readonly",
            "--workdir=/workspace",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            "--env=HOME=/tmp",
            self.settings.sandbox_image,
            "python",
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ]

    def run(self, files: dict[str, str]) -> dict:
        if not self.settings.sandbox_enabled:
            return {"status": "not_run", "reason": "Docker sandbox disabled; no host fallback"}
        if not shutil.which("docker"):
            return {"status": "unavailable", "reason": "Docker executable not installed"}
        if not any(path.startswith("tests/") and path.endswith(".py") for path in files):
            return {
                "status": "unsupported",
                "reason": "Only Python stdlib unittest repositories are supported",
            }
        staging = self.settings.sandbox_staging_dir or self.settings.data_dir / "sandbox"
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging) as temporary:
            directory = Path(temporary)
            directory.chmod(0o755)
            for path, content in files.items():
                safe_path(path)
                target = directory / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                target.chmod(0o644)
            name = "devpilot-" + uuid4().hex
            try:
                process = subprocess.Popen(
                    self.command(directory, name), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
                )
            except OSError:
                return {"status": "unavailable", "reason": "Docker process could not be started"}
            output = bytearray()

            def drain():
                while block := process.stdout.read(4096):
                    # Drain all output, retain only the first 16 KB. No unbounded memory/disk log.
                    output.extend(block[: max(0, 16000 - len(output))])

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            try:
                code = process.wait(timeout=self.settings.sandbox_timeout)
            except subprocess.TimeoutExpired:
                try:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
                finally:
                    process.kill()
                    process.wait(timeout=5)
                    reader.join(timeout=2)
                    process.stdout.close()
                return {"status": "timeout", "reason": "Sandbox wall-clock budget exceeded"}
            reader.join(timeout=3)
            process.stdout.close()
            log = output.decode("utf-8", errors="replace")
            ran_tests = "Ran " in log and "Ran 0 tests" not in log
            return {
                "status": "passed" if code == 0 and ran_tests else "failed",
                "exit_code": code,
                "output": log,
                "command": "python -m unittest discover -s tests -v",
            }
