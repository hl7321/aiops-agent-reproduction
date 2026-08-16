from pathlib import Path

from super_ai.knowledge.chunk_identity import stable_chunk_id
from super_ai.knowledge.chunking import ChunkingConfig, chunk_document_text
from super_ai.knowledge.files import validate_and_extract
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.knowledge_repositories import SqliteKnowledgeDocumentRepository
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database
from super_ai.retrieval.corpus import SqliteRetrievalCorpusSource


def test_stable_chunk_id_reuses_splitter_content_deterministically() -> None:
    chunks = chunk_document_text("abcdef", ChunkingConfig(maxCharacters=3, overlap=0))

    first = stable_chunk_id("doc-a", chunks[0].index, chunks[0].text)
    repeated = stable_chunk_id("doc-a", chunks[0].index, chunks[0].text)
    changed = stable_chunk_id("doc-a", chunks[1].index, chunks[1].text)

    assert first == repeated
    assert first != changed
    assert first.startswith("doc-a:0:")


async def test_retrieval_corpus_is_succeeded_active_and_owner_filter_scoped(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'retrieval.sqlite3'}"
    await upgrade_database(url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=url))
    try:
        now = utc_now()
        async with transaction_scope(runtime.session_factory) as session:
            session.add_all(
                [
                    UserModel(
                        id=user_id,
                        email=f"{user_id}@example.com",
                        password_hash="x",
                        created_at=now,
                        updated_at=now,
                    )
                    for user_id in ("user-a", "user-b")
                ]
            )
            await session.flush()
            repo = SqliteKnowledgeDocumentRepository(session)
            succeeded = await repo.add(
                "user-a",
                "kb-a",
                validate_and_extract("ok.md", "text/markdown", b"succeeded corpus"),
                strategy="paragraph",
                max_characters=None,
                overlap=None,
            )
            pending = await repo.add(
                "user-a",
                "kb-a",
                validate_and_extract("pending.md", "text/markdown", b"pending corpus"),
                strategy="paragraph",
                max_characters=None,
                overlap=None,
            )
            other = await repo.add(
                "user-b",
                "kb-a",
                validate_and_extract("other.md", "text/markdown", b"other corpus"),
                strategy="paragraph",
                max_characters=None,
                overlap=None,
            )
            await repo.set_index_status("user-a", "kb-a", succeeded.id, "succeeded", now)
            await repo.set_index_status("user-b", "kb-a", other.id, "succeeded", now)
        async with transaction_scope(runtime.session_factory) as session:
            repo = SqliteKnowledgeDocumentRepository(session)
            visible = await repo.list_retrieval_corpus(
                "user-a", ("kb-a",), document_ids=(succeeded.id, pending.id, other.id)
            )
            cross_owner = await repo.list_retrieval_corpus(
                "user-b", ("kb-a",), document_ids=(succeeded.id,)
            )
        chunks = await SqliteRetrievalCorpusSource(runtime.session_factory).load(
            "user-a", ("kb-a",), (succeeded.id,)
        )

        assert [record.id for record in visible] == [succeeded.id]
        assert cross_owner == []
        assert [chunk.excerpt for chunk in chunks] == ["succeeded corpus"]
        assert chunks[0].chunk_id == stable_chunk_id(succeeded.id, 0, "succeeded corpus")
    finally:
        await runtime.close()
