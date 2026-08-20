from pathlib import Path

import pytest


@pytest.fixture
def mcp_database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'mcp.sqlite3'}"
