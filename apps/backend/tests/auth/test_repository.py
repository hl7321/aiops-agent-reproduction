from sqlalchemy import select

from super_ai.auth.passwords import PwdlibPasswordManager
from super_ai.auth.service import AuthService
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import AuthSessionModel, UserModel
from super_ai.memory.extended_sqlite.auth_repositories import (
    SqliteAuthSessionRepository,
    SqliteUserRepository,
)
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


async def test_sqlite_auth_repository_never_persists_plain_credentials(
    auth_database_url: str,
) -> None:
    await upgrade_database(auth_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=auth_database_url))
    raw_token = "raw-token-only-returned-to-client"
    try:
        async with transaction_scope(runtime.session_factory) as session:
            service = AuthService(
                SqliteUserRepository(session),
                SqliteAuthSessionRepository(session),
                PwdlibPasswordManager(),
                token_factory=lambda: raw_token,
            )
            user = await service.register(" User@Example.COM ", "correct horse battery staple")
            login = await service.login("user@example.com", "correct horse battery staple")
            assert login.token == raw_token

        async with transaction_scope(runtime.session_factory) as session:
            user_model = await session.scalar(select(UserModel))
            session_model = await session.scalar(select(AuthSessionModel))
            assert user_model is not None
            assert session_model is not None
            assert user_model.email == "user@example.com"
            assert user_model.password_hash.startswith("$argon2")
            assert user_model.password_hash != "correct horse battery staple"
            assert session_model.token_hash != raw_token
            assert len(session_model.token_hash) == 64
            previous_last_seen = session_model.last_seen_at

        async with transaction_scope(runtime.session_factory) as session:
            service = AuthService(
                SqliteUserRepository(session),
                SqliteAuthSessionRepository(session),
                PwdlibPasswordManager(),
            )
            principal = await service.authenticate(raw_token)
            assert principal.user.id == user.id
            session_repository = SqliteAuthSessionRepository(session)
            not_touched = await session_repository.touch(
                principal.session_id,
                "other-user",
                principal.user.created_at,
            )
            not_owned = await session_repository.revoke(
                principal.session_id,
                "other-user",
                principal.user.created_at,
            )
            assert not_touched is None
            assert not_owned is None
            await service.logout(principal)

        async with transaction_scope(runtime.session_factory) as session:
            session_model = await session.scalar(select(AuthSessionModel))
            assert session_model is not None
            assert session_model.last_seen_at >= previous_last_seen
            assert session_model.revoked_at is not None
    finally:
        await runtime.close()
