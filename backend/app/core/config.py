from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", env_prefix="DEVPILOT_", validate_assignment=True
    )
    data_dir: Path = ROOT / ".data"
    database_url: str = ""
    checkpoint_url: str = ""
    api_token: SecretStr = SecretStr("")
    github_token: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_provider: Literal["hash", "openai"] = "hash"
    model_timeout: int = Field(60, ge=5, le=180)
    model_max_tokens: int = Field(3000, ge=256, le=8000)
    token_budget: int = Field(30000, ge=1000, le=200000)
    input_price_per_million: float | None = Field(None, ge=0)
    output_price_per_million: float | None = Field(None, ge=0)
    context_chars: int = Field(24000, ge=2000, le=100000)
    qdrant_url: str = ""
    redis_url: str = ""
    execution_backend: Literal["thread", "rq"] = "thread"
    sandbox_enabled: bool = False
    sandbox_staging_dir: Path | None = None
    sandbox_host_dir: str = ""
    sandbox_image: str = "python:3.12-slim"
    sandbox_timeout: int = Field(30, ge=5, le=120)
    max_files: int = Field(150, ge=1, le=500)
    max_file_bytes: int = 50000
    max_repo_bytes: int = 2000000

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.database_url:
            self.database_url = f"sqlite:///{(self.data_dir / 'devpilot.db').as_posix()}"
        if self.execution_backend == "rq" and not self.redis_url:
            raise ValueError("RQ requires DEVPILOT_REDIS_URL")
