"""诊断 case 的 owner-scoped SQLite adapter。"""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.aiops.cases.models import CaseMaterial, DiagnosisCaseRecord
from super_ai.memory.extended_sqlite.diagnosis_case_models import DiagnosisCaseModel
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
            created_at=utc_now(),
        )
        self._session.add(model)
        await self._session.flush()
        return _record(model)


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
    )
