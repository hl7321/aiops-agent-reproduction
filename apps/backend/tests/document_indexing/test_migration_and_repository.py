from sqlalchemy import inspect, select

from super_ai.background_jobs.models import NewBackgroundJob
from super_ai.document_indexing.models import NewDocumentIndexTask
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_models import UserModel
from super_ai.memory.extended_sqlite.background_job_models import BackgroundJobModel
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.document_index_task_repositories import (
    SqliteDocumentIndexTaskRepository,
)
from super_ai.memory.extended_sqlite.knowledge_models import KnowledgeDocumentModel
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database


async def test_migration_has_domain_columns_without_job_id(indexing_database_url: str) -> None:
    await upgrade_database(indexing_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=indexing_database_url))
    try:
        async with runtime.engine.connect() as connection:
            columns, checks, indexes = await connection.run_sync(
                lambda conn: (
                    {item["name"] for item in inspect(conn).get_columns("document_index_tasks")},
                    {
                        item["name"]
                        for item in inspect(conn).get_check_constraints("document_index_tasks")
                    },
                    {item["name"] for item in inspect(conn).get_indexes("document_index_tasks")},
                )
            )
        assert columns == {
            "id",
            "owner_user_id",
            "knowledge_base_id",
            "document_id",
            "status",
            "failure_reason",
            "retry_of_task_id",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
        }
        assert "job_id" not in columns
        assert "ck_document_index_tasks_status" in checks
        assert "ix_document_index_tasks_owner_document_created" in indexes
        assert "uq_document_index_tasks_active" in indexes
    finally:
        await runtime.close()


async def test_task_and_job_share_resource_id_and_reads_are_owner_scoped(
    indexing_database_url: str,
) -> None:
    await upgrade_database(indexing_database_url)
    runtime = PersistenceRuntime.start(DatabaseSettings(url=indexing_database_url))
    now = utc_now()
    try:
        async with transaction_scope(runtime.session_factory) as session:
            session.add(
                UserModel(
                    id="user-a",
                    email="a@example.com",
                    password_hash="x",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                UserModel(
                    id="user-b",
                    email="b@example.com",
                    password_hash="x",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                KnowledgeDocumentModel(
                    id="doc-a",
                    owner_user_id="user-a",
                    knowledge_base_id="kb-a",
                    filename="a.md",
                    size_bytes=1,
                    mime_type="text/markdown",
                    sha256="a" * 64,
                    uploaded_at=now,
                    index_status="pending",
                    chunking_strategy="paragraph",
                    max_characters=None,
                    overlap=None,
                    indexable_text="hello",
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        async with transaction_scope(runtime.session_factory) as session:
            tasks = SqliteDocumentIndexTaskRepository(session)
            task = await tasks.create("user-a", NewDocumentIndexTask("kb-a", "doc-a"))
            job = await SqliteBackgroundJobStore(session).enqueue(
                "user-a",
                NewBackgroundJob(
                    kind="document.index",
                    resource_type="document_index_task",
                    resource_id=task.id,
                    payload={"taskId": task.id},
                ),
            )
        async with transaction_scope(runtime.session_factory) as session:
            tasks = SqliteDocumentIndexTaskRepository(session)
            assert await tasks.get("user-b", "kb-a", "doc-a", task.id) is None
            found = await tasks.get("user-a", "kb-a", "doc-a", task.id)
            linked = await session.scalar(
                select(BackgroundJobModel).where(
                    BackgroundJobModel.resource_type == "document_index_task",
                    BackgroundJobModel.resource_id == task.id,
                )
            )
            assert found is not None and found.status == "pending"
            assert linked is not None and linked.id == job.id
    finally:
        await runtime.close()
