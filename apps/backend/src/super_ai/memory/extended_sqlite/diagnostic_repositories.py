"""AIOps 诊断 owner-scoped SQLite adapter。"""

from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.aiops.models import (
    DiagnosticEvidenceRecord,
    DiagnosticReportRecord,
    DiagnosticStatus,
    DiagnosticStepRecord,
    DiagnosticStepStatus,
    DiagnosticTaskRecord,
    EvidenceKind,
    GraphCheckpointRecord,
    NewEvidence,
    PlanStep,
    ReportEvidenceLinkRecord,
    ReportMode,
)
from super_ai.memory.extended_sqlite.agent_audit_models import AgentToolCallAuditModel
from super_ai.memory.extended_sqlite.background_job_repositories import SqliteBackgroundJobStore
from super_ai.memory.extended_sqlite.diagnostic_models import (
    DiagnosticEvidenceModel,
    DiagnosticReportModel,
    DiagnosticStepModel,
    DiagnosticTaskModel,
    GraphCheckpointModel,
    ReportEvidenceLinkModel,
)
from super_ai.memory.primitives import new_id, utc_now
from super_ai.memory.sqlite import transaction_scope
from super_ai.project_config import JsonValue


def _require(value: str, label: str) -> str:
    if not value.strip():
        raise ValueError(f"{label} 不得为空")
    return value


class SqliteDiagnosticRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_task(
        self, owner_user_id: str, query: str | None, alerts: list[dict[str, JsonValue]]
    ) -> DiagnosticTaskRecord:
        _require(owner_user_id, "owner_user_id")
        now = utc_now()
        model = DiagnosticTaskModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            status="accepted",
            query=query,
            alerts_json=alerts,
            current_plan_json=[],
            plan_version=0,
            replan_count=0,
            failure_code=None,
            failure_reason=None,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
        )
        self._session.add(model)
        await self._session.flush()
        return _task(model)

    async def list_tasks(self, owner_user_id: str) -> list[DiagnosticTaskRecord]:
        _require(owner_user_id, "owner_user_id")
        models = (
            await self._session.scalars(
                select(DiagnosticTaskModel)
                .where(DiagnosticTaskModel.owner_user_id == owner_user_id)
                .order_by(DiagnosticTaskModel.updated_at.desc(), DiagnosticTaskModel.id.desc())
            )
        ).all()
        return [_task(model) for model in models]

    async def get_task(self, owner_user_id: str, task_id: str) -> DiagnosticTaskRecord | None:
        model = await self._owned_task(owner_user_id, task_id)
        return _task(model) if model is not None else None

    async def transition_task(
        self,
        owner_user_id: str,
        task_id: str,
        status: DiagnosticStatus,
        *,
        failure_code: str | None = None,
        failure_reason: str | None = None,
    ) -> DiagnosticTaskRecord | None:
        model = await self._owned_task(owner_user_id, task_id)
        if model is None:
            return None
        now = utc_now()
        model.status = status
        model.failure_code = failure_code
        model.failure_reason = failure_reason[:1000] if failure_reason else None
        model.updated_at = now
        if status == "running" and model.started_at is None:
            model.started_at = now
        if status in {"succeeded", "failed", "cancelled"}:
            model.completed_at = now
        await self._session.flush()
        return _task(model)

    async def save_plan(
        self,
        owner_user_id: str,
        task_id: str,
        plan: tuple[PlanStep, ...],
        *,
        replan_count: int,
    ) -> DiagnosticTaskRecord | None:
        model = await self._owned_task(owner_user_id, task_id)
        if model is None:
            return None
        model.plan_version += 1
        model.replan_count = replan_count
        model.current_plan_json = [_plan_json(step) for step in plan]
        model.updated_at = utc_now()
        await self._session.flush()
        return _task(model)

    async def start_step(
        self,
        owner_user_id: str,
        task_id: str,
        plan_version: int,
        step: PlanStep,
        *,
        attempt: int,
    ) -> DiagnosticStepRecord:
        if await self._owned_task(owner_user_id, task_id) is None:
            raise ValueError("诊断任务不存在")
        now = utc_now()
        model = DiagnosticStepModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            diagnostic_task_id=task_id,
            plan_version=plan_version,
            position=step.position,
            attempt=attempt,
            tool_name=step.tool_name,
            arguments_json=step.arguments,
            status="running",
            result_summary=None,
            error_message=None,
            started_at=now,
            completed_at=None,
            created_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return _step(model)

    async def finish_step(
        self,
        owner_user_id: str,
        step_id: str,
        status: DiagnosticStepStatus,
        *,
        result_summary: str | None = None,
        error_message: str | None = None,
    ) -> DiagnosticStepRecord | None:
        model = await self._session.scalar(
            select(DiagnosticStepModel).where(
                DiagnosticStepModel.owner_user_id == owner_user_id,
                DiagnosticStepModel.id == step_id,
            )
        )
        if model is None:
            return None
        model.status = status
        model.result_summary = result_summary[:1000] if result_summary else None
        model.error_message = error_message[:1000] if error_message else None
        model.completed_at = utc_now()
        await self._session.flush()
        return _step(model)

    async def list_steps(self, owner_user_id: str, task_id: str) -> list[DiagnosticStepRecord]:
        models = (
            await self._session.scalars(
                select(DiagnosticStepModel)
                .where(
                    DiagnosticStepModel.owner_user_id == owner_user_id,
                    DiagnosticStepModel.diagnostic_task_id == task_id,
                )
                .order_by(
                    DiagnosticStepModel.plan_version,
                    DiagnosticStepModel.position,
                    DiagnosticStepModel.attempt,
                )
            )
        ).all()
        return [_step(model) for model in models]

    async def get_step(
        self, owner_user_id: str, step_id: str
    ) -> DiagnosticStepRecord | None:
        model = await self._session.scalar(
            select(DiagnosticStepModel).where(
                DiagnosticStepModel.owner_user_id == owner_user_id,
                DiagnosticStepModel.id == step_id,
            )
        )
        return _step(model) if model is not None else None

    async def add_evidence(
        self, owner_user_id: str, task_id: str, evidence: NewEvidence
    ) -> DiagnosticEvidenceRecord:
        if await self._owned_task(owner_user_id, task_id) is None:
            raise ValueError("诊断任务不存在")
        if evidence.diagnostic_step_id is not None:
            step_id = await self._session.scalar(
                select(DiagnosticStepModel.id).where(
                    DiagnosticStepModel.owner_user_id == owner_user_id,
                    DiagnosticStepModel.diagnostic_task_id == task_id,
                    DiagnosticStepModel.id == evidence.diagnostic_step_id,
                )
            )
            if step_id is None:
                raise ValueError("证据步骤必须属于同一 owner/task")
        if evidence.tool_call_id is not None:
            audit_id = await self._session.scalar(
                select(AgentToolCallAuditModel.id).where(
                    AgentToolCallAuditModel.owner_user_id == owner_user_id,
                    AgentToolCallAuditModel.diagnostic_task_id == task_id,
                    AgentToolCallAuditModel.tool_call_id == evidence.tool_call_id,
                )
            )
            if audit_id is None:
                raise ValueError("证据工具调用必须属于同一 owner/task")
        model = DiagnosticEvidenceModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            diagnostic_task_id=task_id,
            diagnostic_step_id=evidence.diagnostic_step_id,
            tool_call_id=evidence.tool_call_id,
            kind=evidence.kind,
            source=evidence.source[:500],
            title=evidence.title[:500],
            summary=evidence.summary[:1000],
            content=evidence.content[:20_000],
            metadata_json=evidence.metadata,
            observed_at=evidence.observed_at,
            created_at=utc_now(),
        )
        self._session.add(model)
        await self._session.flush()
        return _evidence(model)

    async def list_evidence(
        self, owner_user_id: str, task_id: str
    ) -> list[DiagnosticEvidenceRecord]:
        models = (
            await self._session.scalars(
                select(DiagnosticEvidenceModel)
                .where(
                    DiagnosticEvidenceModel.owner_user_id == owner_user_id,
                    DiagnosticEvidenceModel.diagnostic_task_id == task_id,
                )
                .order_by(DiagnosticEvidenceModel.created_at, DiagnosticEvidenceModel.id)
            )
        ).all()
        return [_evidence(model) for model in models]

    async def save_checkpoint(
        self, owner_user_id: str, task_id: str, node: str, state: dict[str, JsonValue]
    ) -> GraphCheckpointRecord:
        if await self._owned_task(owner_user_id, task_id) is None:
            raise ValueError("诊断任务不存在")
        latest = await self._session.scalar(
            select(func.max(GraphCheckpointModel.checkpoint_version)).where(
                GraphCheckpointModel.owner_user_id == owner_user_id,
                GraphCheckpointModel.diagnostic_task_id == task_id,
            )
        )
        model = GraphCheckpointModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            diagnostic_task_id=task_id,
            checkpoint_version=int(latest or 0) + 1,
            node=node,
            state_json=state,
            created_at=utc_now(),
        )
        self._session.add(model)
        await self._session.flush()
        return _checkpoint(model)

    async def latest_checkpoint(
        self, owner_user_id: str, task_id: str
    ) -> GraphCheckpointRecord | None:
        model = await self._session.scalar(
            select(GraphCheckpointModel)
            .where(
                GraphCheckpointModel.owner_user_id == owner_user_id,
                GraphCheckpointModel.diagnostic_task_id == task_id,
            )
            .order_by(GraphCheckpointModel.checkpoint_version.desc())
            .limit(1)
        )
        return _checkpoint(model) if model else None

    async def create_report(
        self,
        owner_user_id: str,
        task_id: str,
        markdown: str,
        mode: ReportMode,
        uncertainty: bool,
    ) -> DiagnosticReportRecord:
        if await self._owned_task(owner_user_id, task_id) is None:
            raise ValueError("诊断任务不存在")
        latest = await self._session.scalar(
            select(func.max(DiagnosticReportModel.revision)).where(
                DiagnosticReportModel.owner_user_id == owner_user_id,
                DiagnosticReportModel.diagnostic_task_id == task_id,
            )
        )
        model = DiagnosticReportModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            diagnostic_task_id=task_id,
            revision=int(latest or 0) + 1,
            markdown=markdown,
            generation_mode=mode,
            uncertainty=uncertainty,
            created_at=utc_now(),
        )
        self._session.add(model)
        await self._session.flush()
        return _report(model)

    async def latest_report(
        self, owner_user_id: str, task_id: str
    ) -> DiagnosticReportRecord | None:
        model = await self._session.scalar(
            select(DiagnosticReportModel)
            .where(
                DiagnosticReportModel.owner_user_id == owner_user_id,
                DiagnosticReportModel.diagnostic_task_id == task_id,
            )
            .order_by(DiagnosticReportModel.revision.desc())
            .limit(1)
        )
        return _report(model) if model else None

    async def get_report(
        self, owner_user_id: str, report_id: str
    ) -> DiagnosticReportRecord | None:
        model = await self._session.scalar(
            select(DiagnosticReportModel).where(
                DiagnosticReportModel.owner_user_id == owner_user_id,
                DiagnosticReportModel.id == report_id,
            )
        )
        return _report(model) if model is not None else None

    async def link_evidence(
        self,
        owner_user_id: str,
        task_id: str,
        report_id: str,
        evidence_id: str,
        claim_key: str,
        section: str,
        position: int,
    ) -> ReportEvidenceLinkRecord:
        report = await self._session.scalar(
            select(DiagnosticReportModel.id).where(
                DiagnosticReportModel.owner_user_id == owner_user_id,
                DiagnosticReportModel.diagnostic_task_id == task_id,
                DiagnosticReportModel.id == report_id,
            )
        )
        evidence = await self._session.scalar(
            select(DiagnosticEvidenceModel.id).where(
                DiagnosticEvidenceModel.owner_user_id == owner_user_id,
                DiagnosticEvidenceModel.diagnostic_task_id == task_id,
                DiagnosticEvidenceModel.id == evidence_id,
            )
        )
        if report is None or evidence is None:
            raise ValueError("报告与证据必须属于同一 owner/task")
        model = ReportEvidenceLinkModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            diagnostic_task_id=task_id,
            report_id=report_id,
            evidence_id=evidence_id,
            claim_key=claim_key,
            section=section,
            position=position,
        )
        self._session.add(model)
        await self._session.flush()
        return _link(model)

    async def list_links(self, owner_user_id: str, task_id: str) -> list[ReportEvidenceLinkRecord]:
        models = (
            await self._session.scalars(
                select(ReportEvidenceLinkModel)
                .where(
                    ReportEvidenceLinkModel.owner_user_id == owner_user_id,
                    ReportEvidenceLinkModel.diagnostic_task_id == task_id,
                )
                .order_by(ReportEvidenceLinkModel.position, ReportEvidenceLinkModel.id)
            )
        ).all()
        return [_link(model) for model in models]

    async def _owned_task(self, owner_user_id: str, task_id: str) -> DiagnosticTaskModel | None:
        _require(owner_user_id, "owner_user_id")
        return await self._session.scalar(
            select(DiagnosticTaskModel).where(
                DiagnosticTaskModel.owner_user_id == owner_user_id,
                DiagnosticTaskModel.id == task_id,
            )
        )


class SqliteDiagnosticStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def call(self, method: str, owner_user_id: str, *args: object, **kwargs: object) -> Any:
        async with transaction_scope(self._sessions) as session:
            if method == "append_job_event":
                job_id, event_type, data = args
                return await SqliteBackgroundJobStore(session).append_progress_event(
                    owner_user_id,
                    cast(str, job_id),
                    {"eventType": cast(str, event_type), "data": cast(dict[str, object], data)},
                )
            repository = SqliteDiagnosticRepository(session)
            operation = getattr(repository, method)
            return await operation(owner_user_id, *args, **kwargs)


def _json_object(value: object) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], value)


def _plan_json(step: PlanStep) -> dict[str, JsonValue]:
    return {
        "position": step.position,
        "toolName": step.tool_name,
        "purpose": step.purpose,
        "arguments": step.arguments,
    }


def _task(model: DiagnosticTaskModel) -> DiagnosticTaskRecord:
    alerts = cast(list[dict[str, JsonValue]], model.alerts_json)
    raw_plan = cast(list[dict[str, JsonValue]], model.current_plan_json)
    plan = tuple(_plan_step(item) for item in raw_plan)
    return DiagnosticTaskRecord(
        model.id,
        model.owner_user_id,
        cast(DiagnosticStatus, model.status),
        model.query,
        tuple(alerts),
        plan,
        model.plan_version,
        model.replan_count,
        model.failure_code,
        model.failure_reason,
        model.created_at,
        model.updated_at,
        model.started_at,
        model.completed_at,
    )


def _plan_step(item: dict[str, JsonValue]) -> PlanStep:
    position = item.get("position")
    tool_name = item.get("toolName")
    purpose = item.get("purpose")
    arguments = item.get("arguments")
    if (
        not isinstance(position, int)
        or isinstance(position, bool)
        or not isinstance(tool_name, str)
        or not isinstance(purpose, str)
        or not isinstance(arguments, dict)
    ):
        raise ValueError("持久化诊断计划结构无效")
    return PlanStep(position, tool_name, purpose, cast(dict[str, JsonValue], arguments))


def _step(model: DiagnosticStepModel) -> DiagnosticStepRecord:
    return DiagnosticStepRecord(
        model.id,
        model.owner_user_id,
        model.diagnostic_task_id,
        model.plan_version,
        model.position,
        model.attempt,
        model.tool_name,
        _json_object(model.arguments_json),
        cast(DiagnosticStepStatus, model.status),
        model.result_summary,
        model.error_message,
        model.started_at,
        model.completed_at,
        model.created_at,
    )


def _evidence(model: DiagnosticEvidenceModel) -> DiagnosticEvidenceRecord:
    return DiagnosticEvidenceRecord(
        model.id,
        model.owner_user_id,
        model.diagnostic_task_id,
        model.diagnostic_step_id,
        model.tool_call_id,
        cast(EvidenceKind, model.kind),
        model.source,
        model.title,
        model.summary,
        model.content,
        _json_object(model.metadata_json),
        model.observed_at,
        model.created_at,
    )


def _report(model: DiagnosticReportModel) -> DiagnosticReportRecord:
    return DiagnosticReportRecord(
        model.id,
        model.owner_user_id,
        model.diagnostic_task_id,
        model.revision,
        model.markdown,
        cast(ReportMode, model.generation_mode),
        model.uncertainty,
        model.created_at,
    )


def _link(model: ReportEvidenceLinkModel) -> ReportEvidenceLinkRecord:
    return ReportEvidenceLinkRecord(
        model.id,
        model.owner_user_id,
        model.diagnostic_task_id,
        model.report_id,
        model.evidence_id,
        model.claim_key,
        model.section,
        model.position,
    )


def _checkpoint(model: GraphCheckpointModel) -> GraphCheckpointRecord:
    return GraphCheckpointRecord(
        model.id,
        model.owner_user_id,
        model.diagnostic_task_id,
        model.checkpoint_version,
        model.node,
        _json_object(model.state_json),
        model.created_at,
    )
