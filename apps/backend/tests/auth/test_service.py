from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from super_ai.auth.models import AuthSessionRecord, UserRecord
from super_ai.auth.repositories import DuplicateEmailError
from super_ai.auth.service import AuthService, AuthServiceError


class FakeUsers:
    def __init__(self) -> None:
        self.by_email: dict[str, UserRecord] = {}

    async def add(self, user: UserRecord) -> None:
        if user.email in self.by_email:
            raise DuplicateEmailError
        self.by_email[user.email] = user

    async def get_by_email(self, email: str) -> UserRecord | None:
        return self.by_email.get(email)


class FakeSessions:
    def __init__(self, users: FakeUsers) -> None:
        self.users = users
        self.items: dict[str, AuthSessionRecord] = {}

    async def add(self, session: AuthSessionRecord) -> None:
        self.items[session.id] = session

    async def get_active_with_user(
        self, token_hash: str
    ) -> tuple[AuthSessionRecord, UserRecord] | None:
        for session in self.items.values():
            if session.token_hash == token_hash and session.revoked_at is None:
                user = next(
                    user for user in self.users.by_email.values() if user.id == session.user_id
                )
                return session, user
        return None

    async def touch(
        self, session_id: str, user_id: str, seen_at: datetime
    ) -> AuthSessionRecord | None:
        session = self.items.get(session_id)
        if session is None or session.user_id != user_id or session.revoked_at is not None:
            return None
        touched = AuthSessionRecord(
            id=session.id,
            user_id=session.user_id,
            token_hash=session.token_hash,
            created_at=session.created_at,
            last_seen_at=seen_at,
            revoked_at=None,
        )
        self.items[session.id] = touched
        return touched

    async def revoke(
        self, session_id: str, user_id: str, revoked_at: datetime
    ) -> AuthSessionRecord | None:
        session = self.items.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        revoked = AuthSessionRecord(
            id=session.id,
            user_id=session.user_id,
            token_hash=session.token_hash,
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
            revoked_at=revoked_at,
        )
        self.items[session.id] = revoked
        return revoked


class SpyPasswords:
    def __init__(self) -> None:
        self.verifications: list[tuple[str, str]] = []

    def hash(self, password: str) -> str:
        return f"argon2::{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        self.verifications.append((password, password_hash))
        return password_hash == f"argon2::{password}"


def make_service() -> tuple[AuthService, FakeUsers, FakeSessions, SpyPasswords]:
    users = FakeUsers()
    sessions = FakeSessions(users)
    passwords = SpyPasswords()
    now = datetime(2026, 8, 8, tzinfo=timezone.utc)
    service = AuthService(
        users,
        sessions,
        passwords,
        token_factory=lambda: "raw-token-with-sufficient-entropy",
        clock=lambda: now,
    )
    return service, users, sessions, passwords


async def test_register_normalizes_email_and_records_are_immutable() -> None:
    service, users, _, _ = make_service()
    user = await service.register("  User@Example.COM ", "secret")

    assert user.email == "user@example.com"
    assert users.by_email[user.email].password_hash == "argon2::secret"
    assert users.by_email[user.email].password_hash != "secret"
    with pytest.raises(FrozenInstanceError):
        user.email = "changed@example.com"  # type: ignore[misc]


async def test_duplicate_registration_is_stable_error() -> None:
    service, _, _, _ = make_service()
    await service.register("user@example.com", "secret")

    with pytest.raises(AuthServiceError, match="AUTH_EMAIL_ALREADY_REGISTERED") as error:
        await service.register(" USER@example.com ", "different")

    assert error.value.code == "AUTH_EMAIL_ALREADY_REGISTERED"


async def test_wrong_and_unknown_login_use_same_error_and_dummy_verification() -> None:
    service, _, sessions, passwords = make_service()
    await service.register("user@example.com", "correct")

    for email in ("user@example.com", "missing@example.com"):
        with pytest.raises(AuthServiceError) as error:
            await service.login(email, "wrong")
        assert error.value.code == "AUTH_INVALID_CREDENTIALS"

    assert passwords.verifications[0] == ("wrong", "argon2::correct")
    assert passwords.verifications[1][0] == "wrong"
    assert passwords.verifications[1][1] == service.dummy_password_hash
    assert sessions.items == {}


async def test_login_hashes_token_touches_and_revokes_session() -> None:
    service, _, sessions, _ = make_service()
    user = await service.register("user@example.com", "correct")
    login = await service.login("USER@example.com", "correct")

    session = next(iter(sessions.items.values()))
    assert login.user == user
    assert login.token == "raw-token-with-sufficient-entropy"
    assert session.token_hash == (
        "27eb78e340f836974e2873b37021b55cb238ab91fe16c41ba6657a6b33f5e608"
    )
    assert login.token not in repr(session)

    original_last_seen = session.last_seen_at
    principal = await service.authenticate(login.token)
    assert principal.user == user
    assert sessions.items[session.id].last_seen_at >= original_last_seen

    await service.logout(principal)
    assert sessions.items[session.id].revoked_at is not None
    with pytest.raises(AuthServiceError) as error:
        await service.authenticate(login.token)
    assert error.value.code == "AUTH_REQUIRED"


async def test_owner_safe_session_mutation_rejects_other_user() -> None:
    _, _, sessions, _ = make_service()
    now = datetime(2026, 8, 8, tzinfo=timezone.utc)
    session = AuthSessionRecord(
        user_id="owner", token_hash="0" * 64, created_at=now, last_seen_at=now
    )
    await sessions.add(session)

    assert await sessions.touch(session.id, "other", now + timedelta(seconds=1)) is None
    assert await sessions.revoke(session.id, "other", now + timedelta(seconds=1)) is None
    assert sessions.items[session.id] == session
