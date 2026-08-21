from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from super_ai.chat_configuration.models import ParsedSkillDocument
from super_ai.chat_configuration.store import SqliteChatAgentConfigurationStore
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.chat_configuration_repositories import (
    SqliteChatConfigurationRepository,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import (
    PersistenceRuntime,
    create_sqlite_engine,
    transaction_scope,
    upgrade_database,
)


def _schema(connection: Connection) -> tuple[set[str], set[str]]:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    columns = {item["name"] for item in inspector.get_columns("user_chat_skills")}
    return tables, columns


async def test_migration_creates_exact_three_chat_configuration_tables(
    chat_configuration_database_url: str,
) -> None:
    await upgrade_database(chat_configuration_database_url)
    engine = create_sqlite_engine(DatabaseSettings(url=chat_configuration_database_url))
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables, skill_columns = await connection.run_sync(_schema)
    finally:
        await engine.dispose()
    assert revision == "20260821_0012"
    assert {
        "user_chat_configurations",
        "user_chat_prompts",
        "user_chat_skills",
    }.issubset(tables)
    assert not {"user_chat_skill_selections", "chat_skill_catalog"}.intersection(tables)
    assert {"owner_user_id", "name", "content", "metadata", "is_selected"}.issubset(skill_columns)


async def _seed(runtime: PersistenceRuntime, owner: str) -> None:
    async with transaction_scope(runtime.session_factory) as session:
        now = utc_now()
        session.add(
            UserModel(
                id=owner,
                email=f"{owner}@example.com",
                password_hash="hash",
                created_at=now,
                updated_at=now,
            )
        )


async def test_repository_is_owner_scoped_and_replaces_selection_atomically(
    chat_configuration_database_url: str,
) -> None:
    await upgrade_database(chat_configuration_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=chat_configuration_database_url))
    try:
        await _seed(runtime, "user-a")
        await _seed(runtime, "user-b")
        parsed = ParsedSkillDocument(
            "SKILL.md",
            "knowledge-search",
            "检索知识",
            "BODY",
            {"name": "knowledge-search", "description": "检索知识"},
            "检索知识",
        )
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteChatConfigurationRepository(session)
            prompt = await repository.create_prompt("user-a", "值班", "保持简洁")
            skill = await repository.create_skill("user-a", parsed)
            assert await repository.update_prompt("user-b", prompt.id, "x", "y") is None
            assert await repository.replace_selection("user-a", prompt.id, [skill.id])
        async with transaction_scope(runtime.session_factory) as session:
            current = await SqliteChatConfigurationRepository(session).get("user-a")
            foreign = await SqliteChatConfigurationRepository(session).get("user-b")
        store = SqliteChatAgentConfigurationStore(runtime.session_factory)
        first_snapshot = await store.load_snapshot("user-a")
        async with transaction_scope(runtime.session_factory) as session:
            await SqliteChatConfigurationRepository(session).replace_selection("user-a", None, [])
        next_snapshot = await store.load_snapshot("user-a")
        assert current.selected_prompt_id == prompt.id
        assert [item.id for item in current.skills if item.is_selected] == [skill.id]
        assert foreign.prompts == () and foreign.skills == ()
        assert first_snapshot.user_prompt == "保持简洁"
        assert first_snapshot.allowed_skill_names == frozenset({"knowledge-search"})
        assert not hasattr(first_snapshot.skills[0], "content")
        assert next_snapshot.user_prompt is None
        assert next_snapshot.skills == ()
    finally:
        await runtime.close()
