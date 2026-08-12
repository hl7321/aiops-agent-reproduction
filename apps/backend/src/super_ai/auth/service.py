"""注册、登录和可撤销 session 的领域服务。"""

from collections.abc import Callable
from datetime import datetime
from typing import Literal, TypeAlias

from super_ai.auth.models import AuthPrincipal, AuthSessionRecord, LoginResult, UserRecord
from super_ai.auth.passwords import DUMMY_PASSWORD_HASH, PasswordManager
from super_ai.auth.repositories import AuthSessionRepository, DuplicateEmailError, UserRepository
from super_ai.auth.tokens import generate_token, hash_token
from super_ai.memory.primitives import utc_now

AuthServiceErrorCode: TypeAlias = Literal[
    "AUTH_EMAIL_ALREADY_REGISTERED", "AUTH_INVALID_CREDENTIALS", "AUTH_REQUIRED"
]


class AuthServiceError(Exception):
    def __init__(self, code: AuthServiceErrorCode) -> None:
        super().__init__(code)
        self.code: AuthServiceErrorCode = code


class AuthService:
    dummy_password_hash = DUMMY_PASSWORD_HASH

    def __init__(
        self,
        users: UserRepository,
        sessions: AuthSessionRepository,
        passwords: PasswordManager,
        *,
        token_factory: Callable[[], str] = generate_token,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._passwords = passwords
        self._token_factory = token_factory
        self._clock = clock

    async def register(self, email: str, password: str) -> UserRecord:
        normalized_email = normalize_email(email)
        user = UserRecord(
            email=normalized_email,
            password_hash=self._passwords.hash(password),
        )
        try:
            await self._users.add(user)
        except DuplicateEmailError as error:
            raise AuthServiceError("AUTH_EMAIL_ALREADY_REGISTERED") from error
        return user

    async def login(self, email: str, password: str) -> LoginResult:
        user = await self._users.get_by_email(normalize_email(email))
        password_hash = user.password_hash if user is not None else self.dummy_password_hash
        password_valid = self._passwords.verify(password, password_hash)
        if user is None or not password_valid:
            raise AuthServiceError("AUTH_INVALID_CREDENTIALS")

        raw_token = self._token_factory()
        now = self._now()
        await self._sessions.add(
            AuthSessionRecord(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                created_at=now,
                last_seen_at=now,
            )
        )
        return LoginResult(user=user, token=raw_token)

    async def authenticate(self, raw_token: str) -> AuthPrincipal:
        result = await self._sessions.get_active_with_user(hash_token(raw_token))
        if result is None:
            raise AuthServiceError("AUTH_REQUIRED")
        session, user = result
        touched = await self._sessions.touch(session.id, user.id, self._now())
        if touched is None:
            raise AuthServiceError("AUTH_REQUIRED")
        return AuthPrincipal(user=user, session_id=session.id)

    async def logout(self, principal: AuthPrincipal) -> None:
        revoked = await self._sessions.revoke(
            principal.session_id,
            principal.user.id,
            self._now(),
        )
        if revoked is None:
            raise AuthServiceError("AUTH_REQUIRED")

    def _now(self) -> datetime:
        return self._clock()


def normalize_email(email: str) -> str:
    return email.strip().casefold()
