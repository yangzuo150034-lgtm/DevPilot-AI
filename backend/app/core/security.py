import hashlib
import json
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

DENIED_PARTS = {
    ".git",
    ".env",
    ".venv",
    "node_modules",
    "vendor",
    "__pycache__",
    "dist",
    "build",
    ".aws",
    ".ssh",
    ".codex",
    ".agents",
}
SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".md",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
}


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or len(value) > 250
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError("Invalid repository path")
    return value


def allowed_path(value: str) -> bool:
    try:
        safe_path(value)
    except ValueError:
        return False
    path = PurePosixPath(value)
    return (
        not any(p.lower() in DENIED_PARTS or p.lower().startswith(".env") for p in path.parts)
        and not any(
            p.lower() in {"credentials", "secrets.json", "package-lock.json"} for p in path.parts
        )
        and (
            path.suffix.lower() in SOURCE_SUFFIXES
            or path.name.lower() in {"readme", "license", "dockerfile"}
        )
        and not any(x in path.name.lower() for x in [".pem", ".key", "secret", "credential"])
    )


def github_repo(value: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Only https://github.com/owner/repository URLs are accepted")
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", x) for x in parts):
        raise ValueError("Expected a GitHub repository URL, without a branch or file path")
    if any(x in {".", ".."} for x in parts):
        raise ValueError("Invalid GitHub repository")
    return parts[0], parts[1]


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
