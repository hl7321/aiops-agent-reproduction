from pathlib import Path

import pytest


@pytest.fixture
def chat_configuration_database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'chat-configuration.sqlite3'}"
