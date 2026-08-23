import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import func, select

from super_ai.aiops.cases.service import DiagnosisCasePersistor, LegacyDiagnosisKnowledgeSaver
from super_ai.aiops.models import NewEvidence
from super_ai.api_contracts import KnowledgeRetrievalToolInput
from super_ai.api_responses import AppError
from super_ai.auth.models import UserRecord
from super_ai.feedback.models import FeedbackUpsert
from super_ai.llm.rerank import RerankResult
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.extended_sqlite.auth_repositories import SqliteUserRepository
from super_ai.memory.extended_sqlite.background_job_models import BackgroundJobModel
from super_ai.memory.extended_sqlite.diagnosis_case_models import DiagnosisCaseModel
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticRepository
from super_ai.memory.extended_sqlite.feedback_repositories import SqliteFeedbackRepository
from super_ai.memory.extended_sqlite.knowledge_models import KnowledgeDocumentModel
from super_ai.memory.sqlite import PersistenceRuntime, transaction_scope, upgrade_database
from super_ai.retrieval.corpus import SqliteRetrievalCorpusSource
from super_ai.retrieval.service import KnowledgeRetrievalService
from super_ai.tenancy.context import CurrentUser
from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.records import VectorSearchHit


class _RetrievalProvider:
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.1] * 1024 for _ in texts]

    async def rerank(
        self, query: str, documents: Sequence[str], *, top_n: int
    ) -> list[RerankResult]:
        del query
        return [RerankResult(0, documents[0], 0.9)][:top_n]


class _RetrievalVectors:
    def __init__(self, hit: VectorSearchHit) -> None:
        self._hit = hit

    async def initialize(self) -> None:
        return None

    async def search(
        self, scope: VectorScope, query_vector: Sequence[float], *, limit: int
    ) -> list[VectorSearchHit]:
        del query_vector, limit
        assert scope.owner_user_id == "owner-a"
        return [self._hit]


async def _runtime(path: Path) -> PersistenceRuntime:
    url = f"sqlite+aiosqlite:///{path}"
    await upgrade_database(url)
    return PersistenceRuntime.start(DatabaseSettings(url=url))


async def _successful_task(runtime: PersistenceRuntime, owner: str) -> tuple[str, str]:
    async with transaction_scope(runtime.session_factory) as session:
        await SqliteUserRepository(session).add(
            UserRecord(id=owner, email=f"{owner}@example.com", password_hash="safe-hash")
        )
        repository = SqliteDiagnosticRepository(session)
        task = await repository.create_task(
            owner,
            "checkout error",
            [{"alertName": "HighError", "service": "checkout"}],
        )
        report = await repository.create_report(
            owner,
            task.id,
            "# 告警分析报告\n- 根因结论：连接池耗尽\n- 建议：扩容\n- 整体评估：已定位",
            "model",
            False,
            "verified_evidence",
        )
        evidence = await repository.add_evidence(
            owner,
            task.id,
            NewEvidence(
                kind="log_hit",
                source="SearchLog",
                title="HighError 日志命中",
                summary="连接池耗尽",
                content="incident_id=inc-001 connection pool exhausted",
                metadata={"incidentId": "inc-001"},
            ),
        )
        await repository.link_evidence(
            owner, task.id, report.id, evidence.id, "root-cause", "根因结论", 0
        )
        await SqliteFeedbackRepository(session).upsert(
            owner,
            FeedbackUpsert(
                target_type="diagnostic_report",
                target_id=report.id,
                subject_key="",
                rating="positive",
                reason=None,
                comment="人工确认结论可信",
                correction=None,
            ),
        )
        await repository.transition_task(owner, task.id, "succeeded")
        return task.id, report.id


async def test_successful_report_creates_case_document_and_durable_index_job(
    tmp_path: Path,
) -> None:
    runtime = await _runtime(tmp_path / "case.sqlite3")
    try:
        task_id, report_id = await _successful_task(runtime, "owner-a")
        case = await DiagnosisCasePersistor(runtime.session_factory).persist(
            "owner-a", task_id, report_id
        )
        async with transaction_scope(runtime.session_factory) as session:
            document = await session.get(KnowledgeDocumentModel, case.document_id)
            assert document is not None
            document.index_status = "succeeded"
            jobs = await session.scalar(
                select(func.count()).select_from(BackgroundJobModel).where(
                    BackgroundJobModel.resource_type == "document_index_task",
                    BackgroundJobModel.resource_id == case.index_task_id,
                )
            )
        assert document.source_metadata["knowledgeType"] == "diagnostic-case"
        assert len(case.evidence_ids) == 1
        assert jobs == 1
        chunks = await SqliteRetrievalCorpusSource(runtime.session_factory).load(
            "owner-a", (document.knowledge_base_id,), (document.id,)
        )
        assert chunks and any("HighError" in chunk.excerpt for chunk in chunks)
        assert chunks[0].metadata["sourceDiagnosticTaskId"] == task_id
        target = next(chunk for chunk in chunks if "HighError" in chunk.excerpt)
        retrieval = KnowledgeRetrievalService(
            SqliteRetrievalCorpusSource(runtime.session_factory),
            _RetrievalProvider(),
            _RetrievalVectors(VectorSearchHit(target.chunk_id, 0.9, {})),
        )
        output = await retrieval.retrieve(
            CurrentUser("owner-a"), KnowledgeRetrievalToolInput(query="HighError")
        )
        assert output.results[0].document_id == case.document_id
        assert output.results[0].metadata["knowledgeType"] == "diagnostic-case"
        other = await retrieval.retrieve(
            CurrentUser("owner-b"), KnowledgeRetrievalToolInput(query="HighError")
        )
        assert other.results == []
    finally:
        await runtime.close()


async def test_automatic_path_is_idempotent_and_owner_scoped(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "idempotent.sqlite3")
    try:
        task_id, report_id = await _successful_task(runtime, "owner-a")
        persistor = DiagnosisCasePersistor(runtime.session_factory)
        first = await persistor.persist("owner-a", task_id, report_id)
        second = await persistor.persist("owner-a", task_id, report_id)
        assert first.id == second.id
        with pytest.raises(AppError) as caught:
            await persistor.get("owner-b", first.id)
        assert caught.value.code == "BUSINESS_RESOURCE_NOT_FOUND"
    finally:
        await runtime.close()


async def test_non_successful_task_never_creates_case(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "failed.sqlite3")
    try:
        task_id, report_id = await _successful_task(runtime, "owner-a")
        async with transaction_scope(runtime.session_factory) as session:
            await SqliteDiagnosticRepository(session).transition_task("owner-a", task_id, "failed")
        with pytest.raises(AppError):
            await DiagnosisCasePersistor(runtime.session_factory).persist(
                "owner-a", task_id, report_id
            )
        async with transaction_scope(runtime.session_factory) as session:
            count = await session.scalar(select(func.count()).select_from(DiagnosisCaseModel))
        assert count == 0
    finally:
        await runtime.close()


@pytest.mark.parametrize("status", ["failed", "cancelled"])
async def test_failed_or_cancelled_task_never_creates_case(
    tmp_path: Path, status: Literal["failed", "cancelled"]
) -> None:
    runtime = await _runtime(tmp_path / f"{status}.sqlite3")
    try:
        task_id, report_id = await _successful_task(runtime, "owner-a")
        async with transaction_scope(runtime.session_factory) as session:
            repository = SqliteDiagnosticRepository(session)
            await repository.transition_task("owner-a", task_id, status)
        with pytest.raises(AppError):
            await DiagnosisCasePersistor(runtime.session_factory).persist(
                "owner-a", task_id, report_id
            )
    finally:
        await runtime.close()


async def test_succeeded_task_without_final_report_never_creates_case(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "no-report.sqlite3")
    try:
        async with transaction_scope(runtime.session_factory) as session:
            await SqliteUserRepository(session).add(
                UserRecord(id="owner-a", email="a@example.com", password_hash="safe-hash")
            )
            repository = SqliteDiagnosticRepository(session)
            task = await repository.create_task("owner-a", None, [])
            await repository.transition_task("owner-a", task.id, "succeeded")
        with pytest.raises(AppError):
            await DiagnosisCasePersistor(runtime.session_factory).persist(
                "owner-a", task.id, "missing-report"
            )
    finally:
        await runtime.close()


async def test_legacy_path_creates_assets_without_structured_case_and_conflicts_on_repeat(
    tmp_path: Path,
) -> None:
    runtime = await _runtime(tmp_path / "legacy.sqlite3")
    try:
        task_id, _ = await _successful_task(runtime, "owner-a")
        saver = LegacyDiagnosisKnowledgeSaver(runtime.session_factory)
        saved = await saver.save("owner-a", task_id)
        assert saved.document.id and saved.index_task.id
        with pytest.raises(AppError) as caught:
            await saver.save("owner-a", task_id)
        assert caught.value.code == "BUSINESS_CONFLICT"
        async with transaction_scope(runtime.session_factory) as session:
            count = await session.scalar(select(func.count()).select_from(DiagnosisCaseModel))
        assert count == 0
    finally:
        await runtime.close()


async def test_concurrent_calls_return_one_case(tmp_path: Path) -> None:
    runtime = await _runtime(tmp_path / "concurrent.sqlite3")
    try:
        task_id, report_id = await _successful_task(runtime, "owner-a")
        persistor = DiagnosisCasePersistor(runtime.session_factory)
        results = await asyncio.gather(
            persistor.persist("owner-a", task_id, report_id),
            persistor.persist("owner-a", task_id, report_id),
        )
        assert results[0].id == results[1].id
    finally:
        await runtime.close()
