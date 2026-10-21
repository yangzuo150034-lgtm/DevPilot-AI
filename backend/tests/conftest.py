import pytest

from app.core.config import Settings
from app.service import Service


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        database_url="",
        checkpoint_url="",
        api_token="",
        openai_api_key="",
        github_token="",
        qdrant_url="",
        sandbox_enabled=False,
        embedding_provider="hash",
        execution_backend="thread",
    )


@pytest.fixture
def service(settings):
    instance = Service(settings)
    yield instance
    instance.close()
