"""认证领域可见的不可变 records。"""

from dataclasses import dataclass, field
from datetime import datetime

from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.records import Record


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRecord(Record):
    email: str
    password_hash: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionRecord:
    user_id: str
    token_hash: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    last_seen_at: datetime = field(default_factory=utc_now)
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: UserRecord
    token: str


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    user: UserRecord
    session_id: str
