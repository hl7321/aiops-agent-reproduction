"""Alembic 迁移权威与 metadata 一致性测试。"""

from pathlib import Path

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.app import create_app
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import Base, create_sqlite_engine
from super_ai.memory.sqlite.migrations import upgrade_database

BASELINE_REVISION = "20260813_0005"


def _sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


def _table_names(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names())


async def test_fresh_database_upgrades_to_head(tmp_path: Path) -> None:
    database_path = tmp_path / "fresh.sqlite3"
    url = _sqlite_url(database_path)

    await upgrade_database(url)

    engine = create_sqlite_engine(DatabaseSettings(url=url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()

    assert database_path.exists()
    assert revision == BASELINE_REVISION


async def test_upgrade_creates_missing_sqlite_parent(tmp_path: Path) -> None:
    database_path = tmp_path / "missing" / "nested" / "fresh.sqlite3"

    await upgrade_database(_sqlite_url(database_path))

    assert database_path.exists()


async def test_migrated_business_schema_matches_product_metadata(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "schema.sqlite3")
    await upgrade_database(url)

    engine = create_sqlite_engine(DatabaseSettings(url=url))
    try:
        async with engine.connect() as connection:
            migrated_tables = await connection.run_sync(_table_names)
    finally:
        await engine.dispose()

    migrated_tables.discard("alembic_version")
    assert migrated_tables == set(Base.metadata.tables)


async def test_app_does_not_create_schema_or_run_migrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("应用运行期不得建表或执行迁移")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden)
    monkeypatch.setattr(command, "upgrade", forbidden)

    async with AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}
