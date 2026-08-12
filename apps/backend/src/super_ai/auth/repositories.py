"""认证服务依赖的数据库无关 repository contracts。"""

from datetime import datetime
from typing import Protocol

from super_ai.auth.models import AuthSessionRecord, UserRecord


class DuplicateEmailError(Exception):
    """数据库唯一约束拒绝规范化邮箱。"""


class UserRepository(Protocol):
    async def add(self, user: UserRecord) -> None: ...

    async def get_by_email(self, email: str) -> UserRecord | None: ...


class AuthSessionRepository(Protocol):
    async def add(self, session: AuthSessionRecord) -> None: ...

    async def get_active_with_user(
        self, token_hash: str
    ) -> tuple[AuthSessionRecord, UserRecord] | None: ...

    async def touch(
        self, session_id: str, user_id: str, seen_at: datetime
    ) -> AuthSessionRecord | None: ...

    async def revoke(
        self, session_id: str, user_id: str, revoked_at: datetime
    ) -> AuthSessionRecord | None: ...
