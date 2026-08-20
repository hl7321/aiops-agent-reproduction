from pathlib import Path

import pytest


@pytest.fixture
def agent_audit_database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'agent-audit.sqlite3'}"
