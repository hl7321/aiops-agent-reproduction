"""自动 case 主路径与 legacy 手动保存路径。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.aiops.cases.content import build_case_material
from super_ai.aiops.cases.models import CaseMaterial, DiagnosisCaseRecord
from super_ai.api_responses import AppError
from super_ai.document_indexing.models import DocumentIndexTaskRecord
from super_ai.document_indexing.service import DocumentIndexTaskService
from super_ai.knowledge.chunking import ChunkingConfig
from super_ai.knowledge.files import validate_and_extract
from super_ai.knowledge.models import KnowledgeDocumentRecord
from super_ai.knowledge.service import (
    KnowledgeConflictError,
    KnowledgeDocumentService,
    NoIndexedVectorDeleter,
    default_knowledge_base_id,
)
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.diagnosis_case_repositories import (
    SqliteDiagnosisCaseRepository,
)
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticRepository
from super_ai.memory.extended_sqlite.document_index_task_repositories import (
    SqliteDocumentIndexTaskRepository,
)
from super_ai.memory.extended_sqlite.knowledge_repositories import (
    SqliteKnowledgeDocumentRepository,
)
from super_ai.memory.sqlite import transaction_scope


@dataclass(frozen=True, slots=True)
class SavedDiagnosisKnowledge:
    document: KnowledgeDocumentRecord
    index_task: DocumentIndexTaskRecord


class DiagnosisCasePersistor:
    """按 source task 幂等创建结构化 case、知识文档与 durable index task。"""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def persist(
        self, owner_user_id: str, task_id: str, report_id: str
    ) -> DiagnosisCaseRecord:
        try:
            return await self._persist_once(owner_user_id, task_id, report_id)
        except (KnowledgeConflictError, IntegrityError) as conflict:
            # 并发 loser 的事务已经回滚；winner 提交后按唯一 task scope 读取。
            for _ in range(3):
                async with transaction_scope(self._sessions) as session:
                    winner = await SqliteDiagnosisCaseRepository(session).get_by_task(
                        owner_user_id, task_id
                    )
                    if winner is not None:
                        return winner
                await asyncio.sleep(0)
            raise conflict

    async def _persist_once(
        self, owner_user_id: str, task_id: str, report_id: str
    ) -> DiagnosisCaseRecord:
        async with transaction_scope(self._sessions) as session:
            cases = SqliteDiagnosisCaseRepository(session)
            existing = await cases.get_by_task(owner_user_id, task_id)
            if existing is not None:
                return existing
            diagnostics = SqliteDiagnosticRepository(session)
            task = await diagnostics.get_task(owner_user_id, task_id)
            report = await diagnostics.latest_report(owner_user_id, task_id)
            if (
                task is None
                or task.status != "succeeded"
                or report is None
                or report.id != report_id
            ):
                raise AppError("BUSINESS_RULE_VIOLATION")
            evidence = await diagnostics.list_evidence(owner_user_id, task_id)
            material = build_case_material(
                task_id=task_id,
                report_id=report.id,
                report_markdown=report.markdown,
                alerts=task.alerts,
                evidence_ids=tuple(item.id for item in evidence),
            )
            assets = await _create_knowledge_assets(session, owner_user_id, task_id, material)
            return await cases.create(
                owner_user_id,
                task_id,
                report.id,
                assets.document.id,
                assets.index_task.id,
                material,
            )

    async def list(self, owner_user_id: str) -> list[DiagnosisCaseRecord]:
        async with transaction_scope(self._sessions) as session:
            return await SqliteDiagnosisCaseRepository(session).list(owner_user_id)

    async def get(self, owner_user_id: str, case_id: str) -> DiagnosisCaseRecord:
        async with transaction_scope(self._sessions) as session:
            record = await SqliteDiagnosisCaseRepository(session).get(owner_user_id, case_id)
            if record is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            return record


class LegacyDiagnosisKnowledgeSaver:
    """保留的手动补充路径；有意不写 structured case。"""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(self, owner_user_id: str, task_id: str) -> SavedDiagnosisKnowledge:
        async with transaction_scope(self._sessions) as session:
            diagnostics = SqliteDiagnosticRepository(session)
            task = await diagnostics.get_task(owner_user_id, task_id)
            report = await diagnostics.latest_report(owner_user_id, task_id)
            if task is None:
                raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
            if task.status != "succeeded" or report is None:
                raise AppError("BUSINESS_RULE_VIOLATION")
            evidence = await diagnostics.list_evidence(owner_user_id, task_id)
            material = build_case_material(
                task_id=task_id,
                report_id=report.id,
                report_markdown=report.markdown,
                alerts=task.alerts,
                evidence_ids=tuple(item.id for item in evidence),
            )
            return await _create_knowledge_assets(session, owner_user_id, task_id, material)


async def _create_knowledge_assets(
    session: AsyncSession,
    owner_user_id: str,
    task_id: str,
    material: CaseMaterial,
) -> SavedDiagnosisKnowledge:
    repository = SqliteKnowledgeDocumentRepository(session)
    document_service = KnowledgeDocumentService(repository, NoIndexedVectorDeleter())
    kb = default_knowledge_base_id(owner_user_id)
    filename = f"diagnostic-case-{task_id}.md"
    extracted = validate_and_extract(filename, "text/markdown", material.markdown.encode("utf-8"))
    try:
        document = await document_service.upload(
            owner_user_id,
            kb,
            extracted,
            ChunkingConfig(strategy="markdown-heading"),
            source_metadata=material.source_metadata,
        )
    except (KnowledgeConflictError, IntegrityError):
        raise
    index_task = await DocumentIndexTaskService(
        SqliteDocumentIndexTaskRepository(session), repository, SqliteBackgroundJobStore(session)
    ).create(owner_user_id, kb, document.id)
    return SavedDiagnosisKnowledge(document, index_task)
