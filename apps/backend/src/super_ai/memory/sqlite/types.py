"""SQLite 的稳定 JSON 与 UTC 类型。"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from super_ai.memory.primitives import dump_json, load_json


class UTCDateTime(TypeDecorator[datetime]):
    """写入 UTC naive 值并在读取时恢复 UTC aware 时间。"""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime 不接受 naive datetime")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class CanonicalJson(TypeDecorator[object]):
    """通过统一 codec 将 JSON 值存储为确定性文本。"""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: object | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return dump_json(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> object | None:
        if value is None:
            return None
        return load_json(value)
