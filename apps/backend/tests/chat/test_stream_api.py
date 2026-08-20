from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager

import httpx
from langchain_core.messages import BaseMessage

from super_ai.api_contracts import ChatStreamMessageRequest
from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.chat.dependencies import get_agent_chat_stream_service
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import PersistenceRuntime, upgrade_database

from .test_api import DeterministicSummarizer
from .test_stream_service import ScriptedRunnerFactory, make_service


@asynccontextmanager
async def stream_client_for(
    url: str,
    factory: ScriptedRunnerFactory,
    *,
    context_window_tokens: int = 1000,
    estimate_tokens: Callable[[Sequence[BaseMessage]], int] | None = None,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url),
        worker_settings=WorkerSettings(poll_interval_seconds=60),
        chat_memory_context_window_tokens=1000,
        chat_memory_summarizer=DeterministicSummarizer(),
    )
    async with app.router.lifespan_context(app):
        runtime = app.state.persistence_runtime
        assert isinstance(runtime, PersistenceRuntime)
        service = make_service(
            runtime,
            factory,
            context_window_tokens=context_window_tokens,
            estimate_tokens=estimate_tokens,
        )
        app.dependency_overrides[get_agent_chat_stream_service] = lambda: service
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


async def test_stream_api_returns_ordered_sse_and_persists_complete_answer(
    chat_database_url: str,
) -> None:
    factory = ScriptedRunnerFactory([("中文🙂", None)])
    async with stream_client_for(chat_database_url, factory) as client:
        headers = await _auth(client, "owner@example.com")
        created = await client.post("/chat/sessions", headers=headers)
        session_id = created.json()["data"]["session"]["id"]

        response = await client.post(
            f"/chat/sessions/{session_id}/messages:stream",
            headers={**headers, "X-Request-ID": "req-stream-1"},
            json=ChatStreamMessageRequest(content="你好").model_dump(by_alias=True),
        )
        detail = await client.get(f"/chat/sessions/{session_id}", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["X-Request-ID"] == "req-stream-1"
    data_lines = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
    assert len(data_lines) == 4
    assert response.text.count('"type":"complete"') == 1
    assert [item["role"] for item in detail.json()["data"]["messages"]] == [
        "user", "assistant",
    ]


async def test_stream_api_rejects_foreign_session_before_starting_sse(
    chat_database_url: str,
) -> None:
    factory = ScriptedRunnerFactory([("不应执行", None)])
    async with stream_client_for(chat_database_url, factory) as client:
        owner = await _auth(client, "owner@example.com")
        other = await _auth(client, "other@example.com")
        created = await client.post("/chat/sessions", headers=owner)
        session_id = created.json()["data"]["session"]["id"]

        response = await client.post(
            f"/chat/sessions/{session_id}/messages:stream",
            headers=other,
            json={"content": "越权"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"
    assert factory.runners == []


async def test_stream_api_rejects_95_percent_before_persisting_user(
    chat_database_url: str,
) -> None:
    factory = ScriptedRunnerFactory([("不应执行", None)])
    async with stream_client_for(
        chat_database_url,
        factory,
        context_window_tokens=100,
        estimate_tokens=lambda _messages: 95,
    ) as client:
        headers = await _auth(client, "limit@example.com")
        created = await client.post("/chat/sessions", headers=headers)
        session_id = created.json()["data"]["session"]["id"]
        await client.put(
            f"/chat/sessions/{session_id}/memory",
            headers=headers,
            json={"memoryMode": "manual"},
        )

        response = await client.post(
            f"/chat/sessions/{session_id}/messages:stream",
            headers=headers,
            json={"content": "不能落盘"},
        )
        detail = await client.get(f"/chat/sessions/{session_id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "CHAT_CONTEXT_LIMIT_REACHED",
        "category": "business",
        "httpStatus": 409,
        "message": "会话上下文已达到安全上限，请先手动压缩记忆",
    }
    assert detail.json()["data"]["messages"] == []
    assert factory.runners == []
