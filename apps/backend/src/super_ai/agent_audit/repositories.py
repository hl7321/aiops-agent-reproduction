"""owner-scoped Agent 工具审计 Repository Protocol。"""

from datetime import datetime
from typing import Protocol

from super_ai.agent_audit.models import AgentToolCallAuditRecord, NewAgentToolCallAudit


class AgentToolCallAuditRepository(Protocol):
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

    async def list_for_chat(
        self, owner_user_id: str, chat_session_id: str
    ) -> list[AgentToolCallAuditRecord]: ...

    async def list_for_diagnostic(
        self, owner_user_id: str, diagnostic_task_id: str
    ) -> list[AgentToolCallAuditRecord]: ...
