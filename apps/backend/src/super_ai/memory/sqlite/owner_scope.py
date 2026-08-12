"""把 owner 与资源标识组合进同一 SQL 语句的 SQLite helper。"""

from collections.abc import Mapping, Sequence
from typing import TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.dml import Delete, Update
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

ModelT = TypeVar("ModelT")


def _owner_condition(
    owner_user_id: str,
    owner_column: InstrumentedAttribute[str],
) -> ColumnElement[bool]:
    normalized = owner_user_id.strip()
    if not normalized:
        raise ValueError("owner_user_id 不得为空")
    return owner_column == normalized


def scoped_select(
    model: type[ModelT],
    *,
    owner_user_id: str,
    owner_column: InstrumentedAttribute[str],
    criteria: Sequence[ColumnElement[bool]],
) -> Select[tuple[ModelT]]:
    return select(model).where(_owner_condition(owner_user_id, owner_column), *criteria)


def scoped_child_select(
    model: type[ModelT],
    *,
    owner_user_id: str,
    owner_column: InstrumentedAttribute[str],
    parent_column: InstrumentedAttribute[str],
    parent_id: str,
    child_column: InstrumentedAttribute[str],
    child_id: str,
) -> Select[tuple[ModelT]]:
    return scoped_select(
        model,
        owner_user_id=owner_user_id,
        owner_column=owner_column,
        criteria=(parent_column == parent_id, child_column == child_id),
    )


def scoped_update(
    model: type[object],
    *,
    owner_user_id: str,
    owner_column: InstrumentedAttribute[str],
    criteria: Sequence[ColumnElement[bool]],
    values: Mapping[str, object],
) -> Update:
    return (
        update(model)
        .where(_owner_condition(owner_user_id, owner_column), *criteria)
        .values(**dict(values))
    )


def scoped_delete(
    model: type[object],
    *,
    owner_user_id: str,
    owner_column: InstrumentedAttribute[str],
    criteria: Sequence[ColumnElement[bool]],
) -> Delete:
    return delete(model).where(_owner_condition(owner_user_id, owner_column), *criteria)
