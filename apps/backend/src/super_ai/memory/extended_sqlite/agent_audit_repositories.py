"""Agent 工具调用审计 Repository 的 SQLite adapter。"""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.agent_audit.models import (
    AgentToolCallAuditRecord,
    AgentToolCallAuditStatus,
    NewAgentToolCallAudit,
)
from super_ai.background_jobs.security import redact_error
from super_ai.memory.extended_sqlite.agent_audit_models import AgentToolCallAuditModel
from super_ai.memory.primitives import dump_json, new_id
from super_ai.memory.sqlite import transaction_scope
from super_ai.project_config import JsonValue


class SqliteAgentToolCallAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(
        self, owner_user_id: str, audit: NewAgentToolCallAudit
    ) -> AgentToolCallAuditRecord:
        model = AgentToolCallAuditModel(
            id=new_id(),
            owner_user_id=owner_user_id,
            tool_call_id=audit.tool_call_id,
            chat_session_id=audit.chat_session_id,
            diagnostic_task_id=audit.diagnostic_task_id,
            tool_name=audit.tool_name,
            arguments_json=audit.arguments,
            status="started",
            result_summary=None,
            error_message=None,
            started_at=audit.started_at,
            completed_at=None,
            duration_ms=None,
        )
        self._session.add(model)
        await self._session.flush()
        return _record(model)

    async def complete(
        self,
        owner_user_id: str,
        audit_id: str,
        *,
        result_summary: str,
        completed_at: object,
    ) -> AgentToolCallAuditRecord | None:
        model = await self._owned(owner_user_id, audit_id)
        if model is None:
            return None
        completed = _as_datetime(completed_at)
        model.status = "completed"
        model.result_summary = result_summary[:1000]
        model.error_message = None
        model.completed_at = completed
        model.duration_ms = _duration_ms(model.started_at, completed)
        await self._session.flush()
        return _record(model)

    async def fail(
        self,
        owner_user_id: str,
        audit_id: str,
        *,
        error_message: str,
        completed_at: object,
        api_key: str = "",
    ) -> AgentToolCallAuditRecord | None:
        model = await self._owned(owner_user_id, audit_id)
        if model is None:
            return None
        completed = _as_datetime(completed_at)
        model.status = "failed"
        model.result_summary = None
        model.error_message = redact_error(error_message, dump_json({"apiKey": api_key}))
        model.completed_at = completed
        model.duration_ms = _duration_ms(model.started_at, completed)
        await self._session.flush()
        return _record(model)

    async def list_for_chat(
        self, owner_user_id: str, chat_session_id: str
    ) -> list[AgentToolCallAuditRecord]:
        models = (
            await self._session.scalars(
                select(AgentToolCallAuditModel)
                .where(
                    AgentToolCallAuditModel.owner_user_id == owner_user_id,
                    AgentToolCallAuditModel.chat_session_id == chat_session_id,
                )
                .order_by(AgentToolCallAuditModel.started_at, AgentToolCallAuditModel.id)
            )
        ).all()
        return [_record(model) for model in models]

    async def _owned(
        self, owner_user_id: str, audit_id: str
    ) -> AgentToolCallAuditModel | None:
        return await self._session.scalar(
            select(AgentToolCallAuditModel).where(
                AgentToolCallAuditModel.owner_user_id == owner_user_id,
                AgentToolCallAuditModel.id == audit_id,
            )
        )


def _duration_ms(started_at: object, completed_at: object) -> int:
    started = _as_datetime(started_at)
    completed = _as_datetime(completed_at)
    return max(0, round((completed - started).total_seconds() * 1000))


def _as_datetime(value: object):
    from datetime import datetime

    if not isinstance(value, datetime):
        raise TypeError("审计时间必须是 datetime")
    return value


def _record(model: AgentToolCallAuditModel) -> AgentToolCallAuditRecord:
    return AgentToolCallAuditRecord(
        id=model.id,
        owner_user_id=model.owner_user_id,
        tool_call_id=model.tool_call_id,
        chat_session_id=model.chat_session_id,
        diagnostic_task_id=model.diagnostic_task_id,
        tool_name=model.tool_name,
        arguments=cast(dict[str, JsonValue], model.arguments_json),
        status=cast(AgentToolCallAuditStatus, model.status),
        result_summary=model.result_summary,
        error_message=model.error_message,
        started_at=model.started_at,
        completed_at=model.completed_at,
        duration_ms=model.duration_ms,
    )


class SqliteAgentToolCallAuditStore:
    """每次审计状态变更使用独立短事务。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def start(
        self, owner_user_id: str, audit: NewAgentToolCallAudit
    ) -> AgentToolCallAuditRecord:
        async with transaction_scope(self._sessions) as session:
            return await SqliteAgentToolCallAuditRepository(session).start(owner_user_id, audit)

    async def complete(self, owner_user_id: str, audit_id: str, **values: object):
        async with transaction_scope(self._sessions) as session:
            return await SqliteAgentToolCallAuditRepository(session).complete(
                owner_user_id,
                audit_id,
                result_summary=cast(str, values["result_summary"]),
                completed_at=_as_datetime(values["completed_at"]),
            )

    async def fail(self, owner_user_id: str, audit_id: str, **values: object):
        async with transaction_scope(self._sessions) as session:
            return await SqliteAgentToolCallAuditRepository(session).fail(
                owner_user_id,
                audit_id,
                error_message=cast(str, values["error_message"]),
                completed_at=_as_datetime(values["completed_at"]),
                api_key=cast(str, values.get("api_key", "")),
            )
