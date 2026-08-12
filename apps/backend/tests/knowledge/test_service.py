from super_ai.knowledge.chunking import ChunkingConfig
from super_ai.knowledge.files import validate_and_extract
from super_ai.knowledge.service import (
    KnowledgeConflictError,
    KnowledgeDocumentService,
    default_knowledge_base_id,
)
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.knowledge_repositories import SqliteKnowledgeDocumentRepository
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database
from super_ai.tenancy.context import CurrentUser, OwnerScope


class FakeVectorDeleter:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[OwnerScope, str, str]] = []
        self.fail = fail

    async def delete_document(
        self, scope: OwnerScope, knowledge_base_id: str, document_id: str
    ) -> None:
        self.calls.append((scope, knowledge_base_id, document_id))
        if self.fail:
            raise RuntimeError("milvus unavailable")


async def _runtime(url: str) -> PersistenceRuntime:
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    async with transaction_scope(runtime.session_factory) as session:
        now = utc_now()
        session.add(
            UserModel(
                id="user-a",
                email="a@example.com",
                password_hash="x",
                created_at=now,
                updated_at=now,
            )
        )
    return runtime


async def test_default_kb_is_stable_and_duplicate_requires_overwrite(
    knowledge_database_url: str,
) -> None:
    runtime = await _runtime(knowledge_database_url)
    deleter = FakeVectorDeleter()
    extracted = validate_and_extract("a.md", "text/markdown", b"hello")
    try:
        async with transaction_scope(runtime.session_factory) as session:
            service = KnowledgeDocumentService(SqliteKnowledgeDocumentRepository(session), deleter)
            first = await service.upload(
                "user-a", default_knowledge_base_id("user-a"), extracted, ChunkingConfig()
            )
        try:
            async with transaction_scope(runtime.session_factory) as session:
                await KnowledgeDocumentService(
                    SqliteKnowledgeDocumentRepository(session), deleter
                ).upload("user-a", default_knowledge_base_id("user-a"), extracted, ChunkingConfig())
        except KnowledgeConflictError:
            pass
        else:
            raise AssertionError("duplicate upload should conflict")
        async with transaction_scope(runtime.session_factory) as session:
            second = await KnowledgeDocumentService(
                SqliteKnowledgeDocumentRepository(session), deleter
            ).upload(
                "user-a",
                default_knowledge_base_id("user-a"),
                extracted,
                ChunkingConfig(),
                overwrite=True,
            )
            assert second.id != first.id
        assert deleter.calls[0][1:] == (default_knowledge_base_id("user-a"), first.id)
    finally:
        await runtime.close()


async def test_delete_failure_does_not_soft_delete(knowledge_database_url: str) -> None:
    runtime = await _runtime(knowledge_database_url)
    kb = default_knowledge_base_id("user-a")
    try:
        async with transaction_scope(runtime.session_factory) as session:
            record = await KnowledgeDocumentService(
                SqliteKnowledgeDocumentRepository(session), FakeVectorDeleter()
            ).upload(
                "user-a",
                kb,
                validate_and_extract("a.md", "text/markdown", b"hello"),
                ChunkingConfig(),
            )
        try:
            async with transaction_scope(runtime.session_factory) as session:
                await KnowledgeDocumentService(
                    SqliteKnowledgeDocumentRepository(session), FakeVectorDeleter(fail=True)
                ).delete("user-a", kb, record.id)
        except RuntimeError:
            pass
        async with transaction_scope(runtime.session_factory) as session:
            assert (
                await SqliteKnowledgeDocumentRepository(session).get("user-a", kb, record.id)
                is not None
            )
    finally:
        await runtime.close()


def test_default_kb_differs_by_user_and_matches_current_user() -> None:
    assert default_knowledge_base_id("user-a") == default_knowledge_base_id(
        CurrentUser("user-a").user_id
    )
    assert default_knowledge_base_id("user-a") != default_knowledge_base_id("user-b")
