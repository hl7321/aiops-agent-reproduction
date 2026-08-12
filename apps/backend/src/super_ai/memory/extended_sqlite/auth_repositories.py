"""认证 Repository Protocol 的 SQLite adapter。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.auth.models import AuthSessionRecord, UserRecord
from super_ai.auth.repositories import DuplicateEmailError
from super_ai.memory.extended_sqlite.auth_models import AuthSessionModel, UserModel


class SqliteUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: UserRecord) -> None:
        self._session.add(_user_to_model(user))
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise DuplicateEmailError from error

    async def get_by_email(self, email: str) -> UserRecord | None:
        model = await self._session.scalar(select(UserModel).where(UserModel.email == email))
        return _user_to_record(model) if model is not None else None


class SqliteAuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session: AuthSessionRecord) -> None:
        self._session.add(_session_to_model(session))
        await self._session.flush()

    async def get_active_with_user(
        self, token_hash: str
    ) -> tuple[AuthSessionRecord, UserRecord] | None:
        statement = (
            select(AuthSessionModel, UserModel)
            .join(UserModel, UserModel.id == AuthSessionModel.user_id)
            .where(
                AuthSessionModel.token_hash == token_hash,
                AuthSessionModel.revoked_at.is_(None),
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return _session_to_record(row[0]), _user_to_record(row[1])

    async def touch(
        self, session_id: str, user_id: str, seen_at: datetime
    ) -> AuthSessionRecord | None:
        model = await self._owned_active_session(session_id, user_id)
        if model is None:
            return None
        model.last_seen_at = seen_at
        await self._session.flush()
        return _session_to_record(model)

    async def revoke(
        self, session_id: str, user_id: str, revoked_at: datetime
    ) -> AuthSessionRecord | None:
        model = await self._owned_active_session(session_id, user_id)
        if model is None:
            return None
        model.revoked_at = revoked_at
        await self._session.flush()
        return _session_to_record(model)

    async def _owned_active_session(
        self, session_id: str, user_id: str
    ) -> AuthSessionModel | None:
        return await self._session.scalar(
            select(AuthSessionModel).where(
                AuthSessionModel.id == session_id,
                AuthSessionModel.user_id == user_id,
                AuthSessionModel.revoked_at.is_(None),
            )
        )


def _user_to_model(user: UserRecord) -> UserModel:
    return UserModel(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _user_to_record(model: UserModel) -> UserRecord:
    return UserRecord(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _session_to_model(session: AuthSessionRecord) -> AuthSessionModel:
    return AuthSessionModel(
        id=session.id,
        user_id=session.user_id,
        token_hash=session.token_hash,
        created_at=session.created_at,
        last_seen_at=session.last_seen_at,
        revoked_at=session.revoked_at,
    )


def _session_to_record(model: AuthSessionModel) -> AuthSessionRecord:
    return AuthSessionRecord(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        created_at=model.created_at,
        last_seen_at=model.last_seen_at,
        revoked_at=model.revoked_at,
    )
