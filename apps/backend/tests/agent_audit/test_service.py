import logging
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from super_ai.agent_audit.models import AgentToolCallAuditRecord, NewAgentToolCallAudit
from super_ai.agent_audit.service import AgentToolAuditService
from super_ai.tenancy.context import CurrentUser

NOW = datetime(2026, 8, 18, 0, 0, tzinfo=timezone.utc)


class FakeAuditWriter:
    def __init__(self) -> None:
        self.records: dict[str, AgentToolCallAuditRecord] = {}
        self.last_fail_values: dict[str, object] = {}

    async def start(
        self, owner_user_id: str, audit: NewAgentToolCallAudit
    ) -> AgentToolCallAuditRecord:
        record = AgentToolCallAuditRecord(
            id="audit-1",
            owner_user_id=owner_user_id,
            tool_call_id=audit.tool_call_id,
            chat_session_id=audit.chat_session_id,
            diagnostic_task_id=audit.diagnostic_task_id,
            tool_name=audit.tool_name,
            arguments=audit.arguments,
            status="started",
            result_summary=None,
            error_message=None,
            started_at=audit.started_at,
            completed_at=None,
            duration_ms=None,
        )
        self.records[record.id] = record
        return record

    async def complete(self, owner_user_id: str, audit_id: str, **values: object):
        current = self.records[audit_id]
        completed = replace(
            current,
            status="completed",
            result_summary=values["result_summary"],
            completed_at=values["completed_at"],
            duration_ms=0,
        )
        self.records[audit_id] = completed
        return completed

    async def fail(self, owner_user_id: str, audit_id: str, **values: object):
        self.last_fail_values = values
        current = self.records[audit_id]
        failed = replace(
            current,
            status="failed",
            error_message="safe failure",
            completed_at=values["completed_at"],
            duration_ms=0,
        )
        self.records[audit_id] = failed
        return failed


async def test_service_audits_completed_tool_and_logs_only_argument_keys(
    caplog: pytest.LogCaptureFixture,
) -> None:
    writer = FakeAuditWriter()
    service = AgentToolAuditService(writer, now=lambda: NOW)

    async def operation() -> dict[str, object]:
        return {"results": [{"secretOutput": "OUTPUT_SENTINEL"}]}

    with caplog.at_level(logging.INFO):
        result = await service.execute(
            CurrentUser("user-a"),
            chat_session_id="session-a",
            diagnostic_task_id=None,
            tool_call_id="call-1",
            tool_name="knowledge_retrieval",
            arguments={"query": "QUERY_SENTINEL", "apiKey": "SECRET_SENTINEL"},
            operation=operation,
        )

    assert result == {"results": [{"secretOutput": "OUTPUT_SENTINEL"}]}
    assert writer.records["audit-1"].status == "completed"
    assert "query" in caplog.text and "apiKey" in caplog.text
    for forbidden in ["QUERY_SENTINEL", "SECRET_SENTINEL", "OUTPUT_SENTINEL"]:
        assert forbidden not in caplog.text


async def test_service_audits_failed_tool_without_swallowing_error() -> None:
    writer = FakeAuditWriter()
    service = AgentToolAuditService(writer, now=lambda: NOW, api_key="SECRET_SENTINEL")

    async def operation() -> dict[str, object]:
        raise RuntimeError("provider failed SECRET_SENTINEL")

    with pytest.raises(RuntimeError, match="provider failed"):
        await service.execute(
            CurrentUser("user-a"),
            chat_session_id="session-a",
            diagnostic_task_id=None,
            tool_call_id="call-1",
            tool_name="knowledge_retrieval",
            arguments={"query": "QUERY_SENTINEL"},
            operation=operation,
        )

    assert writer.records["audit-1"].status == "failed"
    assert writer.last_fail_values["api_key"] == "SECRET_SENTINEL"
