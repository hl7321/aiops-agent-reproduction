"""诊断 case 的 owner-scoped SQLite adapter。"""

from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.aiops.cases.models import (
    CaseMaterial,
    DiagnosisCaseRecord,
    DiagnosticCaseSourceRecord,
)
from super_ai.memory.extended_sqlite.diagnosis_case_models import (
    DiagnosisCaseModel,
    DiagnosticCaseSourceModel,
)
from super_ai.memory.primitives import new_id, utc_now


class SqliteDiagnosisCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_task(
        self, owner_user_id: str, task_id: str
    ) -> DiagnosisCaseRecord | None:
        model = await self._session.scalar(
            select(DiagnosisCaseModel).where(
                DiagnosisCaseModel.owner_user_id == owner_user_id,
                DiagnosisCaseModel.task_id == task_id,
            )
        )
        return _record(model) if model else None

    async def get(self, owner_user_id: str, case_id: str) -> DiagnosisCaseRecord | None:
        model = await self._session.scalar(
            select(DiagnosisCaseModel).where(
                DiagnosisCaseModel.owner_user_id == owner_user_id,
                DiagnosisCaseModel.id == case_id,
            )
        )
        return _record(model) if model else None

    async def list(self, owner_user_id: str) -> list[DiagnosisCaseRecord]:
        models = (
            await self._session.scalars(
                select(DiagnosisCaseModel)
                .where(DiagnosisCaseModel.owner_user_id == owner_user_id)
                .order_by(DiagnosisCaseModel.created_at.desc(), DiagnosisCaseModel.id.desc())
            )
        ).all()
        return [_record(model) for model in models]

    async def create(
        self,
        owner_user_id: str,
        task_id: str,
        report_id: str,
        document_id: str,
        index_task_id: str,
        material: CaseMaterial,
        *,
        incident_fingerprint: str | None = None,
        knowledge_fingerprint: str | None = None,
        fingerprint_version: str | None = None,
        promotion_status: str = "legacy",
    ) -> DiagnosisCaseRecord:
        model = DiagnosisCaseModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            task_id=task_id,
            report_id=report_id,
            document_id=document_id,
            index_task_id=index_task_id,
            alert_name=material.alert_name,
            service=material.service,
            keywords=list(material.keywords),
            root_cause=material.root_cause,
            remediation=material.remediation,
            summary=material.summary,
            evidence_ids=list(material.evidence_ids),
            incident_fingerprint=incident_fingerprint,
            knowledge_fingerprint=knowledge_fingerprint,
            fingerprint_version=fingerprint_version,
            promotion_status=promotion_status,
            created_at=utc_now(),
        )
        self._session.add(model)
        await self._session.flush()
        return _record(model)

    async def get_by_incident_fingerprint(
        self, owner_user_id: str, incident_fingerprint: str
    ) -> DiagnosisCaseRecord | None:
        model = await self._session.scalar(
            select(DiagnosisCaseModel).where(
                DiagnosisCaseModel.owner_user_id == owner_user_id,
                DiagnosisCaseModel.incident_fingerprint == incident_fingerprint,
            )
        )
        return _record(model) if model else None

    async def get_by_knowledge_fingerprint(
        self, owner_user_id: str, knowledge_fingerprint: str
    ) -> DiagnosisCaseRecord | None:
        model = await self._session.scalar(
            select(DiagnosisCaseModel).where(
                DiagnosisCaseModel.owner_user_id == owner_user_id,
                DiagnosisCaseModel.knowledge_fingerprint == knowledge_fingerprint,
            )
        )
        return _record(model) if model else None

    async def get_source_by_report(
        self, owner_user_id: str, report_id: str
    ) -> DiagnosticCaseSourceRecord | None:
        model = await self._session.scalar(
            select(DiagnosticCaseSourceModel).where(
                DiagnosticCaseSourceModel.owner_user_id == owner_user_id,
                DiagnosticCaseSourceModel.report_id == report_id,
            )
        )
        return _source_record(model) if model else None

    async def add_source(
        self,
        owner_user_id: str,
        case_id: str,
        diagnostic_task_id: str,
        report_id: str,
        approval_feedback_id: str,
        evidence_ids: tuple[str, ...],
    ) -> DiagnosticCaseSourceRecord:
        case = await self._session.scalar(
            select(DiagnosisCaseModel.id).where(
                DiagnosisCaseModel.owner_user_id == owner_user_id,
                DiagnosisCaseModel.id == case_id,
            )
        )
        if case is None:
            raise ValueError("canonical case 必须属于当前 owner")
        model = DiagnosticCaseSourceModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            case_id=case_id,
            diagnostic_task_id=diagnostic_task_id,
            report_id=report_id,
            approval_feedback_id=approval_feedback_id,
            evidence_ids=list(evidence_ids),
            created_at=utc_now(),
        )
        self._session.add(model)
        await self._session.flush()
        return _source_record(model)

    async def list_sources(
        self, owner_user_id: str, case_id: str
    ) -> list[DiagnosticCaseSourceRecord]:
        models = (
            await self._session.scalars(
                select(DiagnosticCaseSourceModel)
                .where(
                    DiagnosticCaseSourceModel.owner_user_id == owner_user_id,
                    DiagnosticCaseSourceModel.case_id == case_id,
                )
                .order_by(DiagnosticCaseSourceModel.created_at, DiagnosticCaseSourceModel.id)
            )
        ).all()
        return [_source_record(model) for model in models]


def _record(model: DiagnosisCaseModel) -> DiagnosisCaseRecord:
    return DiagnosisCaseRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        task_id=model.task_id,
        report_id=model.report_id,
        document_id=model.document_id,
        index_task_id=model.index_task_id,
        alert_name=model.alert_name,
        service=model.service,
        keywords=tuple(cast(list[str], model.keywords)),
        root_cause=model.root_cause,
        remediation=model.remediation,
        summary=model.summary,
        evidence_ids=tuple(cast(list[str], model.evidence_ids)),
        created_at=model.created_at,
        incident_fingerprint=model.incident_fingerprint,
        knowledge_fingerprint=model.knowledge_fingerprint,
        fingerprint_version=model.fingerprint_version,
        promotion_status=model.promotion_status,
    )


def _source_record(model: DiagnosticCaseSourceModel) -> DiagnosticCaseSourceRecord:
    return DiagnosticCaseSourceRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        case_id=model.case_id,
        diagnostic_task_id=model.diagnostic_task_id,
        report_id=model.report_id,
        approval_feedback_id=model.approval_feedback_id,
        evidence_ids=tuple(cast(list[str], model.evidence_ids)),
        created_at=model.created_at,
    )
