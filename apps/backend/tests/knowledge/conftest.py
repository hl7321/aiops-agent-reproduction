from pathlib import Path

import pytest


@pytest.fixture
def knowledge_database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'knowledge.sqlite3'}"
