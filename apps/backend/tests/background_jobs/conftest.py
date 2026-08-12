from pathlib import Path

import pytest


@pytest.fixture
def jobs_database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'jobs-test.sqlite3'}"
