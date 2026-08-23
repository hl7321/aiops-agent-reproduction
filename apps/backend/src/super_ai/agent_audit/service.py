"""工具调用生命周期审计与安全运行日志。"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol, TypeVar

from super_ai.agent_audit.models import AgentToolCallAuditRecord, NewAgentToolCallAudit
from super_ai.project_config import JsonValue
from super_ai.tenancy.context import CurrentUser

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AgentAuditWriter(Protocol):
    async def start(
        self, owner_user_id: str, audit: NewAgentToolCallAudit
    ) -> AgentToolCallAuditRecord: ...

    async def complete(
        self,
        owner_user_id: str,
        audit_id: str,
        *,
        result_summary: str,
        completed_at: datetime,
    ) -> AgentToolCallAuditRecord | None: ...

    async def fail(
        self,
        owner_user_id: str,
        audit_id: str,
        *,
        error_message: str,
        completed_at: datetime,
        api_key: str = "",
    ) -> AgentToolCallAuditRecord | None: ...


class AgentToolAuditService:
    def __init__(
        self,
        writer: AgentAuditWriter,
        *,
        now: Callable[[], datetime],
        api_key: str = "",
        sensitive_tool_names: frozenset[str] = frozenset(),
    ) -> None:
        self._writer = writer
        self._now = now
        self._api_key = api_key
        self._sensitive_tool_names = sensitive_tool_names
        self._audit_ids: dict[str, str] = {}
        self._tool_names: dict[str, str] = {}

    async def start_tool(
        self,
        current_user: CurrentUser,
        *,
        chat_session_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> None:
        record = await self._writer.start(
            current_user.owner_user_id,
            NewAgentToolCallAudit(
                tool_call_id=tool_call_id,
                chat_session_id=chat_session_id,
                diagnostic_task_id=None,
                tool_name=tool_name,
                arguments=arguments,
                started_at=self._now(),
            ),
        )
        self._audit_ids[tool_call_id] = record.id
        self._tool_names[tool_call_id] = tool_name
        _log_lifecycle(current_user, chat_session_id, tool_name, tool_call_id, arguments, "started")

    async def complete_tool(self, current_user: CurrentUser, tool_call_id: str) -> None:
        audit_id = self._audit_ids[tool_call_id]
        tool_name = self._tool_names[tool_call_id]
        completed = await self._writer.complete(
            current_user.owner_user_id,
            audit_id,
            result_summary=(
                "MCP 工具调用成功"
                if tool_name in self._sensitive_tool_names
                else "工具调用成功"
            ),
            completed_at=self._now(),
        )
        _log_lifecycle(
            current_user,
            completed.chat_session_id if completed is not None else None,
            completed.tool_name if completed is not None else "tool",
            tool_call_id,
            completed.arguments if completed is not None else {},
            "completed",
            duration_ms=completed.duration_ms if completed is not None else None,
        )

    async def fail_tool(
        self, current_user: CurrentUser, tool_call_id: str, *, error: Exception
    ) -> None:
        audit_id = self._audit_ids[tool_call_id]
        failed = await self._writer.fail(
            current_user.owner_user_id,
            audit_id,
            error_message=str(error),
            completed_at=self._now(),
            api_key=self._api_key,
        )
        _log_lifecycle(
            current_user,
            failed.chat_session_id if failed is not None else None,
            failed.tool_name if failed is not None else "tool",
            tool_call_id,
            failed.arguments if failed is not None else {},
            "failed",
            duration_ms=failed.duration_ms if failed is not None else None,
        )

    async def execute(
        self,
        current_user: CurrentUser,
        *,
        chat_session_id: str | None,
        diagnostic_task_id: str | None,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, JsonValue],
        operation: Callable[[], Awaitable[T]],
        api_key: str = "",
    ) -> T:
        started = await self._writer.start(
            current_user.owner_user_id,
            NewAgentToolCallAudit(
                tool_call_id=tool_call_id,
                chat_session_id=chat_session_id,
                diagnostic_task_id=diagnostic_task_id,
                tool_name=tool_name,
                arguments=arguments,
                started_at=self._now(),
            ),
        )
        argument_keys = ",".join(sorted(arguments))
        logger.info(
            "agent tool started owner=%s parent=%s tool=%s call=%s argument_keys=%s",
            current_user.owner_user_id,
            chat_session_id or diagnostic_task_id,
            tool_name,
            tool_call_id,
            argument_keys,
        )
        try:
            result = await operation()
        except Exception as error:
            completed_at = self._now()
            failed = await self._writer.fail(
                current_user.owner_user_id,
                started.id,
                error_message=str(error),
                completed_at=completed_at,
                api_key=api_key or self._api_key,
            )
            logger.info(
                "agent tool failed owner=%s parent=%s tool=%s call=%s duration_ms=%s "
                "argument_keys=%s",
                current_user.owner_user_id,
                chat_session_id or diagnostic_task_id,
                tool_name,
                tool_call_id,
                failed.duration_ms if failed is not None else None,
                argument_keys,
            )
            raise
        completed = await self._writer.complete(
            current_user.owner_user_id,
            started.id,
            result_summary="工具调用成功",
            completed_at=self._now(),
        )
        logger.info(
            "agent tool completed owner=%s parent=%s tool=%s call=%s duration_ms=%s "
            "argument_keys=%s",
            current_user.owner_user_id,
            chat_session_id or diagnostic_task_id,
            tool_name,
            tool_call_id,
            completed.duration_ms if completed is not None else None,
            argument_keys,
        )
        return result

    async def record_failed_attempt(
        self,
        current_user: CurrentUser,
        *,
        diagnostic_task_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, JsonValue],
        error_message: str,
    ) -> None:
        """为调用前校验失败写一条完整 failed audit，不触发外部工具。"""
        started = await self._writer.start(
            current_user.owner_user_id,
            NewAgentToolCallAudit(
                tool_call_id=tool_call_id,
                chat_session_id=None,
                diagnostic_task_id=diagnostic_task_id,
                tool_name=tool_name,
                arguments=arguments,
                started_at=self._now(),
            ),
        )
        await self._writer.fail(
            current_user.owner_user_id,
            started.id,
            error_message=error_message,
            completed_at=self._now(),
            api_key=self._api_key,
        )
        logger.info(
            "agent tool validation failed owner=%s parent=%s tool=%s call=%s argument_keys=%s",
            current_user.owner_user_id,
            diagnostic_task_id,
            tool_name,
            tool_call_id,
            ",".join(sorted(arguments)),
        )


def _log_lifecycle(
    current_user: CurrentUser,
    parent_id: str | None,
    tool_name: str,
    tool_call_id: str,
    arguments: dict[str, JsonValue],
    status: str,
    *,
    duration_ms: int | None = None,
) -> None:
    logger.info(
        "agent tool %s owner=%s parent=%s tool=%s call=%s duration_ms=%s argument_keys=%s",
        status,
        current_user.owner_user_id,
        parent_id,
        tool_name,
        tool_call_id,
        duration_ms,
        ",".join(sorted(arguments)),
    )
