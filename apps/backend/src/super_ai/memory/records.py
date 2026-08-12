"""与 ORM 解耦的不可变 record。"""

from dataclasses import dataclass, field
from datetime import datetime

from super_ai.memory.primitives import new_id, utc_now


@dataclass(frozen=True, slots=True, kw_only=True)
class Record:
    """后续领域 record 可复用的不可变身份与时间字段。"""

    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
