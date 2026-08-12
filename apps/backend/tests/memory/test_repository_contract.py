"""数据库无关 Repository 合同与 SQLite adapter 测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError, dataclass
from datetime import datetime

import pytest
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite import SqliteRepository
from super_ai.memory.records import Record
from super_ai.memory.repository import Repository
from super_ai.memory.sqlite import PersistenceRuntime, UTCDateTime, transaction_scope


@dataclass(frozen=True, slots=True, kw_only=True)
class _WidgetRecord(Record):
    name: str


class _TestBase(DeclarativeBase):
    pass


class _WidgetModel(_TestBase):
    __tablename__ = "repository_widgets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class _WidgetRepository(SqliteRepository[_WidgetRecord, _WidgetModel]):
    model_type = _WidgetModel

    def to_model(self, record: _WidgetRecord) -> _WidgetModel:
        return _WidgetModel(
            id=record.id,
            name=record.name,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def to_record(self, model: _WidgetModel) -> _WidgetRecord:
        return _WidgetRecord(
            id=model.id,
            name=model.name,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


@pytest.fixture
async def runtime(sqlite_database_url: str) -> AsyncIterator[PersistenceRuntime]:
    value = PersistenceRuntime.start(DatabaseSettings(url=sqlite_database_url))
    async with value.engine.begin() as connection:
        await connection.run_sync(_TestBase.metadata.create_all)
    try:
        yield value
    finally:
        await value.close()


async def _assert_repository_contract(repository: Repository[_WidgetRecord]) -> _WidgetRecord:
    record = _WidgetRecord(name="alpha")

    await repository.add(record)
    loaded = await repository.get(record.id)

    assert loaded == record
    assert isinstance(loaded, _WidgetRecord)
    with pytest.raises(FrozenInstanceError):
        loaded.name = "changed"  # type: ignore[misc]
    return record


async def test_sqlite_repository_satisfies_record_contract(
    runtime: PersistenceRuntime,
) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        created = await _assert_repository_contract(_WidgetRepository(session))

    async with transaction_scope(runtime.session_factory) as session:
        loaded = await _WidgetRepository(session).get(created.id)

    assert loaded == created


async def test_sqlite_repository_returns_none_for_unknown_id(
    runtime: PersistenceRuntime,
) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        loaded = await _WidgetRepository(session).get("missing")

    assert loaded is None
