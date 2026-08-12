"""数据库配置边界测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from super_ai.memory.config import load_database_settings


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_user_database_url_overrides_project_url(tmp_path: Path) -> None:
    project_path = _write_json(
        tmp_path / "project.json",
        {
            "database": {
                "url": "sqlite+aiosqlite:///project.sqlite3",
                "echo": False,
            }
        },
    )
    user_path = _write_json(
        tmp_path / "user.project.json",
        {"database": {"url": "sqlite+aiosqlite:///user.sqlite3"}},
    )

    settings = load_database_settings(project_path, user_path)

    assert settings.url == "sqlite+aiosqlite:///user.sqlite3"
    assert settings.echo is False


def test_database_settings_only_read_explicit_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///environment.sqlite3")
    project_path = _write_json(tmp_path / "project.json", {"frontend": {"title": "test"}})
    user_path = _write_json(tmp_path / "user.project.json", {})

    with pytest.raises(ValidationError) as error:
        load_database_settings(project_path, user_path)

    assert "database" in str(error.value)
    assert "environment.sqlite3" not in str(error.value)


@pytest.mark.parametrize(
    "database",
    [
        {"url": "", "echo": False},
        {"url": "not a sqlalchemy url", "echo": False},
        {"url": "sqlite+aiosqlite:///memory.sqlite3", "echo": "yes"},
        {"url": "sqlite+aiosqlite:///memory.sqlite3", "unknown": True},
    ],
)
def test_database_settings_reject_invalid_values(tmp_path: Path, database: object) -> None:
    project_path = _write_json(tmp_path / "project.json", {"database": database})
    user_path = _write_json(tmp_path / "user.project.json", {})

    with pytest.raises(ValidationError):
        load_database_settings(project_path, user_path)
