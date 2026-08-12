"""SQLAlchemy 声明式 metadata 与字段约定。"""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite.types import UTCDateTime


class Base(AsyncAttrs, DeclarativeBase):
    """产品 ORM model 的统一 metadata；P03 不注册领域表。"""


class IdTimestampMixin:
    """后续规范化领域表复用的 ID 与 UTC 时间列。"""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        onupdate=utc_now,
    )
