from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx

from super_ai.agent_audit.models import AgentToolCallAuditRecord
from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.chat.dependencies import get_agent_audit_repository
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import upgrade_database


class FakeAuditRepository:
    def __init__(self, item: AgentToolCallAuditRecord) -> None:
        self.item = item
        self.calls: list[tuple[str, str]] = []

    async def list_for_chat(
        self, owner_user_id: str, chat_session_id: str
    ) -> list[AgentToolCallAuditRecord]:
        self.calls.append((owner_user_id, chat_session_id))
        return [self.item]


@asynccontextmanager
async def audit_client_for(
    url: str, repository: FakeAuditRepository
) -> AsyncGenerator[httpx.AsyncClient, None]:
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url),
        worker_settings=WorkerSettings(poll_interval_seconds=60),
        chat_memory_context_window_tokens=1000,
    )
    app.dependency_overrides[get_agent_audit_repository] = lambda: repository
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            yield client


async def _auth(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    await client.post("/auth/register", json={"email": email, "password": "correct-password"})
    response = await client.post(
        "/auth/login", json={"email": email, "password": "correct-password"}
    )
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


async def test_owner_lists_tool_audits_in_success_envelope(
    agent_audit_database_url: str,
) -> None:
    now = utc_now()
    repository = FakeAuditRepository(
        AgentToolCallAuditRecord(
            id="audit-1",
            owner_user_id="hidden-owner",
            tool_call_id="call-1",
            chat_session_id="session-placeholder",
            diagnostic_task_id=None,
            tool_name="knowledge_retrieval",
            arguments={"query": "订单服务"},
            status="completed",
            result_summary="工具调用成功",
            error_message=None,
            started_at=now,
            completed_at=now,
            duration_ms=3,
        )
    )
    async with audit_client_for(agent_audit_database_url, repository) as client:
        headers = await _auth(client, "owner@example.com")
        created = await client.post("/chat/sessions", headers=headers)
        session_id = created.json()["data"]["session"]["id"]

        response = await client.get(
            f"/chat/sessions/{session_id}/tool-call-audits",
            headers={**headers, "X-Request-ID": "req-audits-1"},
        )

    assert response.status_code == 200
    assert response.json()["meta"]["requestId"] == "req-audits-1"
    item = response.json()["data"]["items"][0]
    assert item["toolCallId"] == "call-1"
    assert item["arguments"] == {"query": "订单服务"}
    assert "ownerUserId" not in item and "parentCallId" not in item
    assert repository.calls[0][1] == session_id


async def test_foreign_or_missing_parent_returns_same_403_before_audit_query(
    agent_audit_database_url: str,
) -> None:
    now = utc_now()
    repository = FakeAuditRepository(
        AgentToolCallAuditRecord(
            "audit-1", "owner", "call-1", "session", None, "tool", {}, "started",
            None, None, now, None, None,
        )
    )
    async with audit_client_for(agent_audit_database_url, repository) as client:
        owner = await _auth(client, "owner@example.com")
        other = await _auth(client, "other@example.com")
        created = await client.post("/chat/sessions", headers=owner)
        session_id = created.json()["data"]["session"]["id"]

        foreign = await client.get(
            f"/chat/sessions/{session_id}/tool-call-audits", headers=other
        )
        missing = await client.get(
            "/chat/sessions/missing/tool-call-audits", headers=other
        )
        unauthenticated = await client.get(
            f"/chat/sessions/{session_id}/tool-call-audits"
        )

    assert foreign.status_code == missing.status_code == 403
    assert foreign.json()["error"]["code"] == missing.json()["error"]["code"] == "AUTH_FORBIDDEN"
    assert unauthenticated.status_code == 401
    assert repository.calls == []
