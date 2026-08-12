from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlalchemy import String, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from super_ai.api_responses import AppError
from super_ai.memory.sqlite.owner_scope import (
    scoped_child_select,
    scoped_delete,
    scoped_select,
    scoped_update,
)
from super_ai.tenancy.errors import require_scoped_parent, require_scoped_resource


class TenantTestBase(AsyncAttrs, DeclarativeBase):
    pass


class Resource(TenantTestBase):
    __tablename__ = "tenant_test_resources"
    owner_user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(64))


class ChildResource(TenantTestBase):
    __tablename__ = "tenant_test_children"
    owner_user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(64))


async def _session(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'scope.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(TenantTestBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def test_two_users_cannot_read_update_or_delete_each_others_resource(
    tmp_path: Path,
) -> None:
    engine, factory = await _session(tmp_path)
    try:
        async with factory.begin() as session:
            session.add_all([
                Resource(owner_user_id="user-a", id="same-id", value="a"),
                Resource(owner_user_id="user-b", id="same-id", value="b"),
                Resource(owner_user_id="user-a", id="only-a", value="safe"),
            ])
        async with factory.begin() as session:
            visible = await session.scalar(scoped_select(
                Resource,
                owner_user_id="user-b",
                owner_column=Resource.owner_user_id,
                criteria=(Resource.id == "same-id",),
            ))
            assert visible is not None and visible.value == "b"

            updated = cast(
                CursorResult[Any],
                await session.execute(scoped_update(
                    Resource,
                    owner_user_id="user-b",
                    owner_column=Resource.owner_user_id,
                    criteria=(Resource.id == "only-a",),
                    values={"value": "hacked"},
                )),
            )
            deleted = cast(
                CursorResult[Any],
                await session.execute(scoped_delete(
                    Resource,
                    owner_user_id="user-b",
                    owner_column=Resource.owner_user_id,
                    criteria=(Resource.id == "only-a",),
                )),
            )
            assert updated.rowcount == deleted.rowcount == 0
        async with factory.begin() as session:
            remaining = await session.scalar(select(Resource).where(Resource.id == "only-a"))
            assert remaining is not None and remaining.value == "safe"
    finally:
        await engine.dispose()


async def test_parent_child_query_contains_owner_parent_and_child_scope(tmp_path: Path) -> None:
    engine, factory = await _session(tmp_path)
    try:
        async with factory.begin() as session:
            session.add(ChildResource(
                owner_user_id="user-a", parent_id="parent-a", id="child-1", value="secret"
            ))
        async with factory.begin() as session:
            invisible = await session.scalar(scoped_child_select(
                ChildResource,
                owner_user_id="user-b",
                owner_column=ChildResource.owner_user_id,
                parent_column=ChildResource.parent_id,
                parent_id="parent-a",
                child_column=ChildResource.id,
                child_id="child-1",
            ))
            assert invisible is None
    finally:
        await engine.dispose()


def test_missing_and_cross_owner_resources_have_non_enumerable_errors() -> None:
    for _case in ("missing", "cross-owner"):
        value = None
        try:
            require_scoped_resource(value)
        except AppError as error:
            assert error.code == "BUSINESS_RESOURCE_NOT_FOUND"
            assert error.details is None
        else:
            raise AssertionError("不可见资源未返回 not found")

        try:
            require_scoped_parent(value)
        except AppError as error:
            assert error.code == "AUTH_FORBIDDEN"
            assert error.details is None
        else:
            raise AssertionError("不可见父资源未返回 forbidden")


def test_empty_owner_scope_is_rejected_before_sql_is_built() -> None:
    for owner_user_id in ("", " "):
        try:
            scoped_select(
                Resource,
                owner_user_id=owner_user_id,
                owner_column=Resource.owner_user_id,
                criteria=(Resource.id == "resource",),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("空 owner scope 未被拒绝")
