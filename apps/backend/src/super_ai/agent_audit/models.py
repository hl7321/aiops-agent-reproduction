"""Agent 工具调用审计的不可变 records。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

from super_ai.project_config import JsonValue

AgentToolCallAuditStatus: TypeAlias = Literal["started", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class NewAgentToolCallAudit:
    tool_call_id: str
    chat_session_id: str | None
    diagnostic_task_id: str | None
    tool_name: str
    arguments: dict[str, JsonValue]
    started_at: datetime

    def __post_init__(self) -> None:
        if (self.chat_session_id is None) == (self.diagnostic_task_id is None):
            raise ValueError("chat_session_id 与 diagnostic_task_id 必须恰好提供一个")


@dataclass(frozen=True, slots=True)
class AgentToolCallAuditRecord:
    id: str
    owner_user_id: str
    tool_call_id: str
    chat_session_id: str | None
    diagnostic_task_id: str | None
    tool_name: str
    arguments: dict[str, JsonValue]
    status: AgentToolCallAuditStatus
    result_summary: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
