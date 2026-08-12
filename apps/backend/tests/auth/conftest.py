from pathlib import Path

import pytest


@pytest.fixture
def auth_database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'auth-test.sqlite3'}"
