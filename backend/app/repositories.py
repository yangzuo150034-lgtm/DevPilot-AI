"""Import immutable text snapshots without cloning or executing repository code."""

import base64
import time

import httpx

from app.core.config import Settings
from app.core.security import allowed_path, digest, github_repo

DEMO_FILES = {
    "calculator.py": '"""Small arithmetic module used by the DevPilot demo."""\n\n\ndef add(a, b):\n    """Return the sum of two numbers."""\n    return a - b\n\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError("division by zero")\n    return a / b\n',
    "tests/test_calculator.py": "import unittest\nfrom calculator import add, divide\n\n\nclass CalculatorTests(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n        self.assertEqual(add(-2, 3), 1)\n\n    def test_divide(self):\n        self.assertEqual(divide(8, 2), 4)\n        with self.assertRaises(ValueError):\n            divide(1, 0)\n",
    "README.md": "# Calculator demo\n\nThe add function should return a sum.\nRun stdlib tests with python -m unittest discover -s tests.\n",
}


def demo_snapshot() -> dict:
    return {
        "name": "demo/calculator",
        "url": "demo://calculator",
        "commit": digest(DEMO_FILES),
        "files": dict(DEMO_FILES),
        "stats": {"source": "bundled-demo", "files": len(DEMO_FILES), "excluded": 0},
    }


def import_github(url: str, settings: Settings, transport=None) -> dict:
    owner, name = github_repo(url)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "DevPilot-AI"}
    token = settings.github_token.get_secret_value()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(
        base_url="https://api.github.com",
        headers=headers,
        timeout=20,
        follow_redirects=False,
        trust_env=False,
        transport=transport,
    ) as client:

        def get(path):
            response = client.get(path)
            if response.status_code == 403 or response.status_code == 429:
                raise ValueError("GitHub access denied or API rate limit reached")
            if response.status_code != 200:
                raise ValueError(f"GitHub import failed: HTTP {response.status_code}")
            return response.json()

        root = f"/repos/{owner}/{name}"
        commit = get(root + "/commits/HEAD")["sha"]
        tree = get(root + f"/git/trees/{commit}?recursive=1")
        if tree.get("truncated"):
            raise ValueError("Repository tree is too large; choose a smaller repository")
        blobs = [item for item in tree["tree"] if item.get("type") == "blob"]
        eligible = [
            item
            for item in blobs
            if (
                item.get("mode") == "100644"
                and allowed_path(item["path"])
                and 0 < item.get("size", 0) <= settings.max_file_bytes
            )
        ]
        eligible.sort(key=lambda item: (item["path"].count("/"), item["path"]))
        files, total, excluded = {}, 0, len(blobs) - len(eligible)
        started = time.monotonic()
        for item in eligible[: settings.max_files]:
            if time.monotonic() - started > 90:
                break
            # Both path and blob size were checked before fetching; verify decoded bytes too.
            blob = get(root + f"/git/blobs/{item['sha']}")
            if blob.get("encoding") != "base64":
                excluded += 1
                continue
            raw = base64.b64decode(blob["content"])
            if len(raw) > settings.max_file_bytes or b"\x00" in raw:
                excluded += 1
                continue
            if total + len(raw) > settings.max_repo_bytes:
                excluded += 1
                continue
            try:
                files[item["path"]] = raw.decode("utf-8")
            except UnicodeDecodeError:
                excluded += 1
                continue
            total += len(raw)
        if not files:
            raise ValueError("No eligible UTF-8 source files found")
    return {
        "name": f"{owner}/{name}",
        "url": f"https://github.com/{owner}/{name}",
        "commit": commit,
        "files": files,
        "stats": {
            "source": "github",
            "files": len(files),
            "bytes": total,
            "excluded": excluded + max(0, len(eligible) - settings.max_files),
            "partial": len(files) != len(blobs),
        },
    }
