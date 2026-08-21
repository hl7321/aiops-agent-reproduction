from sqlalchemy import inspect

from super_ai.feedback.models import FeedbackUpsert
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.feedback_repositories import SqliteFeedbackRepository
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import (
    PersistenceRuntime,
    create_sqlite_engine,
    transaction_scope,
    upgrade_database,
)


async def test_feedback_migration_has_stable_unique_subject_key(
    feedback_database_url: str,
) -> None:
    await upgrade_database(feedback_database_url)
    engine = create_sqlite_engine(DatabaseSettings(url=feedback_database_url))
    try:
        async with engine.connect() as connection:
            columns, uniques, indexes, revision = await connection.run_sync(
                lambda sync: (
                    {item["name"]: item for item in inspect(sync).get_columns("user_feedback")},
                    inspect(sync).get_unique_constraints("user_feedback"),
                    inspect(sync).get_indexes("user_feedback"),
                    sync.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one(),
                )
            )
    finally:
        await engine.dispose()
    assert revision == "20260821_0013"
    assert columns["subject_key"]["nullable"] is False
    assert any(item["column_names"] == [
        "owner_user_id", "target_type", "target_id", "subject_key"
    ] for item in uniques)
    assert any(item["name"] == "ix_user_feedback_owner_target" for item in indexes)


async def test_repository_upsert_preserves_identity_and_delete_is_owner_scoped(
    feedback_database_url: str,
) -> None:
    await upgrade_database(feedback_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=feedback_database_url))
    try:
        async with transaction_scope(runtime.session_factory) as session:
            now = utc_now()
            session.add_all([
                UserModel(
                    id="owner-a", email="a@example.com", password_hash="x",
                    created_at=now, updated_at=now,
                ),
                UserModel(
                    id="owner-b", email="b@example.com", password_hash="x",
                    created_at=now, updated_at=now,
                ),
            ])
        value = FeedbackUpsert(
            "chat_message", "message-1", "", "positive", None, None, None
        )
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteFeedbackRepository(session)
            first = await repository.upsert("owner-a", value)
            second = await repository.upsert(
                "owner-a",
                FeedbackUpsert(
                    "chat_message", "message-1", "", "negative", "incorrect", "错", None
                ),
            )
        assert first.id == second.id
        assert second.subject_key == ""
        assert second.rating == "negative"
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteFeedbackRepository(session)
            assert not await repository.delete("owner-b", first.id)
            assert await repository.delete("owner-a", first.id)
    finally:
        await runtime.close()
