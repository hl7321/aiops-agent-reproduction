"""人工认可后的 canonical case 提升与 legacy 安全补充路径。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.aiops.cases.content import build_case_material
from super_ai.aiops.cases.fingerprints import (
    FINGERPRINT_VERSION,
    case_fingerprints,
    case_similarity,
)
from super_ai.aiops.cases.models import (
    CaseMaterial,
    DiagnosisCaseCandidate,
    DiagnosisCasePromotionResult,
    DiagnosisCaseRecord,
)
from super_ai.aiops.models import DiagnosticTaskRecord
from super_ai.api_responses import AppError
from super_ai.document_indexing.models import DocumentIndexTaskRecord
from super_ai.document_indexing.service import DocumentIndexTaskService
from super_ai.feedback.models import FeedbackRecord
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
from super_ai.memory.extended_sqlite.feedback_repositories import SqliteFeedbackRepository
from super_ai.memory.extended_sqlite.knowledge_repositories import (
    SqliteKnowledgeDocumentRepository,
)
from super_ai.memory.sqlite import transaction_scope

PromotionResolution = Literal["create_new", "merge"]
SIMILARITY_THRESHOLD = 0.30


@dataclass(frozen=True, slots=True)
class SavedDiagnosisKnowledge:
    document: KnowledgeDocumentRecord
    index_task: DocumentIndexTaskRecord


@dataclass(frozen=True, slots=True)
class ApprovedDiagnosis:
    task: DiagnosticTaskRecord
    report_id: str
    feedback: FeedbackRecord
    material: CaseMaterial


class DiagnosisCasePromoter:
    """重新验证 owner、可信报告、provenance 与正向反馈后显式提升。"""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def promote(
        self,
        owner_user_id: str,
        task_id: str,
        *,
        resolution: PromotionResolution | None = None,
        candidate_case_id: str | None = None,
    ) -> DiagnosisCasePromotionResult:
        try:
            return await self._promote_once(
                owner_user_id,
                task_id,
                resolution=resolution,
                candidate_case_id=candidate_case_id,
            )
        except (KnowledgeConflictError, IntegrityError) as conflict:
            for _ in range(4):
                async with transaction_scope(self._sessions) as session:
                    cases = SqliteDiagnosisCaseRepository(session)
                    diagnostics = SqliteDiagnosticRepository(session)
                    report = await diagnostics.latest_report(owner_user_id, task_id)
                    if report is not None:
                        source = await cases.get_source_by_report(owner_user_id, report.id)
                        if source is not None:
                            winner = await cases.get(owner_user_id, source.case_id)
                            if winner is not None:
                                return DiagnosisCasePromotionResult("existing", winner)
                await asyncio.sleep(0)
            raise conflict

    async def _promote_once(
        self,
        owner_user_id: str,
        task_id: str,
        *,
        resolution: PromotionResolution | None,
        candidate_case_id: str | None,
    ) -> DiagnosisCasePromotionResult:
        async with transaction_scope(self._sessions) as session:
            approved = await _approved_diagnosis(session, owner_user_id, task_id)
            cases = SqliteDiagnosisCaseRepository(session)
            source = await cases.get_source_by_report(owner_user_id, approved.report_id)
            if source is not None:
                existing = await cases.get(owner_user_id, source.case_id)
                if existing is None:
                    raise RuntimeError("case source 指向不可见 canonical case")
                return DiagnosisCasePromotionResult("existing", existing)

            incident_fingerprint, knowledge_fingerprint = case_fingerprints(
                approved.material, approved.task.alerts
            )
            canonical_material = replace(
                approved.material,
                source_metadata={
                    **approved.material.source_metadata,
                    "incidentFingerprint": incident_fingerprint,
                    "knowledgeFingerprint": knowledge_fingerprint,
                    "fingerprintVersion": FINGERPRINT_VERSION,
                },
            )
            exact = await cases.get_by_incident_fingerprint(
                owner_user_id, incident_fingerprint
            )
            if exact is None:
                exact = await cases.get_by_knowledge_fingerprint(
                    owner_user_id, knowledge_fingerprint
                )
            if exact is not None:
                await cases.add_source(
                    owner_user_id,
                    exact.id,
                    task_id,
                    approved.report_id,
                    approved.feedback.id,
                    approved.material.evidence_ids,
                )
                return DiagnosisCasePromotionResult("existing", exact)

            candidates = tuple(
                DiagnosisCaseCandidate(item, score)
                for item in await cases.list(owner_user_id)
                if (score := case_similarity(approved.material, item)) >= SIMILARITY_THRESHOLD
            )
            if resolution == "merge":
                selected = next(
                    (item for item in candidates if item.item.id == candidate_case_id), None
                )
                if selected is None:
                    raise AppError("BUSINESS_RULE_VIOLATION")
                await cases.add_source(
                    owner_user_id,
                    selected.item.id,
                    task_id,
                    approved.report_id,
                    approved.feedback.id,
                    approved.material.evidence_ids,
                )
                return DiagnosisCasePromotionResult("merged", selected.item)
            if candidates and resolution != "create_new":
                return DiagnosisCasePromotionResult("needs_review", None, candidates)

            assets = await _create_knowledge_assets(
                session, owner_user_id, task_id, canonical_material
            )
            created = await cases.create(
                owner_user_id,
                task_id,
                approved.report_id,
                assets.document.id,
                assets.index_task.id,
                canonical_material,
                incident_fingerprint=incident_fingerprint,
                knowledge_fingerprint=knowledge_fingerprint,
                fingerprint_version=FINGERPRINT_VERSION,
                promotion_status="canonical",
            )
            await cases.add_source(
                owner_user_id,
                created.id,
                task_id,
                approved.report_id,
                approved.feedback.id,
                approved.material.evidence_ids,
            )
            return DiagnosisCasePromotionResult("created", created)


class DiagnosisCasePersistor:
    """兼容查询入口；旧 persist 也必须经过新的反馈审批门禁。"""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def persist(
        self, owner_user_id: str, task_id: str, report_id: str
    ) -> DiagnosisCaseRecord:
        async with transaction_scope(self._sessions) as session:
            latest = await SqliteDiagnosticRepository(session).latest_report(
                owner_user_id, task_id
            )
        if latest is None or latest.id != report_id:
            raise AppError("BUSINESS_RULE_VIOLATION")
        result = await DiagnosisCasePromoter(self._sessions).promote(owner_user_id, task_id)
        if result.item is None:
            raise AppError("BUSINESS_RULE_VIOLATION")
        return result.item

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
    """保留的手动补充路径；同样不能绕过可信报告与正向反馈。"""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(self, owner_user_id: str, task_id: str) -> SavedDiagnosisKnowledge:
        async with transaction_scope(self._sessions) as session:
            approved = await _approved_diagnosis(session, owner_user_id, task_id)
            return await _create_knowledge_assets(
                session, owner_user_id, task_id, approved.material
            )


async def _approved_diagnosis(
    session: AsyncSession, owner_user_id: str, task_id: str
) -> ApprovedDiagnosis:
    diagnostics = SqliteDiagnosticRepository(session)
    task = await diagnostics.get_task(owner_user_id, task_id)
    if task is None:
        raise AppError("BUSINESS_RESOURCE_NOT_FOUND")
    report = await diagnostics.latest_report(owner_user_id, task_id)
    if (
        task.status != "succeeded"
        or report is None
        or report.trust_state != "verified_evidence"
        or report.uncertainty
    ):
        raise AppError("BUSINESS_RULE_VIOLATION")
    links = [
        item
        for item in await diagnostics.list_links(owner_user_id, task_id)
        if item.report_id == report.id
    ]
    evidence = await diagnostics.list_evidence(owner_user_id, task_id)
    visible_evidence_ids = {item.id for item in evidence}
    linked_ids = tuple(dict.fromkeys(item.evidence_id for item in links))
    if not linked_ids or any(item not in visible_evidence_ids for item in linked_ids):
        raise AppError("BUSINESS_RULE_VIOLATION")
    feedback = await SqliteFeedbackRepository(session).get_subject(
        owner_user_id, "diagnostic_report", report.id, ""
    )
    if feedback is None or feedback.rating != "positive":
        raise AppError("BUSINESS_RULE_VIOLATION")
    material = build_case_material(
        task_id=task_id,
        report_id=report.id,
        report_markdown=report.markdown,
        alerts=task.alerts,
        evidence_ids=linked_ids,
    )
    return ApprovedDiagnosis(task, report.id, feedback, material)


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
    document = await document_service.upload(
        owner_user_id,
        kb,
        extracted,
        ChunkingConfig(strategy="markdown-heading"),
        source_metadata=material.source_metadata,
    )
    index_task = await DocumentIndexTaskService(
        SqliteDocumentIndexTaskRepository(session), repository, SqliteBackgroundJobStore(session)
    ).create(owner_user_id, kb, document.id)
    return SavedDiagnosisKnowledge(document, index_task)
