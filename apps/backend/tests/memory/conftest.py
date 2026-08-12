"""所有持久化测试共享的临时 SQLite fixture。"""

from pathlib import Path

import pytest


@pytest.fixture
def sqlite_database_url(tmp_path: Path) -> str:
    """返回当前测试 tmp_path 下的 aiosqlite 文件 URL。"""
    return f"sqlite+aiosqlite:///{tmp_path / 'memory-test.sqlite3'}"
