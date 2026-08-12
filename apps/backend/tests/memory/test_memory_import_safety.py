"""memory 模块导入安全测试。"""

import subprocess
import sys
from pathlib import Path


def test_importing_memory_modules_has_no_database_side_effects(tmp_path: Path) -> None:
    script = """
from unittest.mock import patch
from pwdlib import PasswordHash

with (
    patch("aiosqlite.connect", side_effect=AssertionError("import connected SQLite")),
    patch("alembic.command.upgrade", side_effect=AssertionError("import ran migration")),
    patch.object(PasswordHash, "hash", side_effect=AssertionError("import hashed password")),
):
    import super_ai.memory
    import super_ai.memory.sqlite
    import super_ai.memory.extended_sqlite
    import super_ai.auth
    import super_ai.auth.dependencies
    import super_ai.memory.extended_sqlite.auth_models
    import super_ai.memory.extended_sqlite.auth_repositories
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
