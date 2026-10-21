import os

import pytest

from app.harness.sandbox import DockerSandbox
from app.repositories import DEMO_FILES

pytestmark = pytest.mark.skipif(
    os.getenv("DEVPILOT_TEST_DOCKER") != "1",
    reason="Requires explicitly enabled Docker integration environment",
)


def test_actual_docker_baseline_fails_and_patch_passes(settings):
    settings.sandbox_enabled = True
    sandbox = DockerSandbox(settings)
    baseline = sandbox.run(DEMO_FILES)
    assert baseline["status"] == "failed", baseline
    files = dict(DEMO_FILES)
    files["calculator.py"] = files["calculator.py"].replace("return a - b", "return a + b")
    candidate = sandbox.run(files)
    assert candidate["status"] == "passed", candidate
