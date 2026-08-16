from pathlib import Path

import pytest


@pytest.fixture
def indexing_database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'indexing.sqlite3'}"
