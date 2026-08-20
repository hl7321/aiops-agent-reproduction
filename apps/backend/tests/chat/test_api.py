import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

import httpx
from sqlalchemy import text

from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import create_sqlite_engine, upgrade_database


class DeterministicSummarizer:
    async def summarize(
        self, previous_summary: str | None, messages: Sequence[str]
    ) -> str:
        return f"{previous_summary or ''} {' '.join(messages)}".strip()


@asynccontextmanager
async def client_for(url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url),
        worker_settings=WorkerSettings(poll_interval_seconds=60),
        chat_memory_context_window_tokens=1000,
        chat_memory_summarizer=DeterministicSummarizer(),
    )
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


async def test_chat_crud_title_metadata_clear_and_delete(chat_database_url: str) -> None:
    async with client_for(chat_database_url) as client:
        headers = await _auth(client, "owner@example.com")
        created = await client.post("/chat/sessions", headers=headers)
        session_id = created.json()["data"]["session"]["id"]
        assistant = await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"role": "assistant", "content": "先回应", "metadata": {}},
        )
        user = await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={
                "role": "user",
                "content": "  这是\n第一条   用户消息" + "长" * 60,
                "metadata": {
                    "references": [{
                        "chunkId": "chunk-1", "documentId": "doc-1",
                        "knowledgeBaseId": "kb-1", "source": "runbook.md",
                    }],
                    "toolCallIds": ["call-1"],
                },
            },
        )
        later = await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"role": "user", "content": "不能覆盖标题"},
        )
        listed = await client.get("/chat/sessions", headers=headers)
        cleared = await client.post(
            f"/chat/sessions/{session_id}/messages:clear", headers=headers
        )
        restarted = await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"role": "user", "content": "重新开始"},
        )
        deleted = await client.delete(f"/chat/sessions/{session_id}", headers=headers)

    assert created.status_code == 201
    assert created.json()["data"]["session"] | {
        "memoryMode": "context_70_percent",
        "memorySummary": None,
        "compactedMessageCount": 0,
        "lastCompactedAt": None,
        "canCompact": False,
        "contextWindowTokens": 1000,
    } == created.json()["data"]["session"]
    assert assistant.json()["data"]["session"]["title"] == "新会话"
    title = user.json()["data"]["session"]["title"]
    assert len(title) == 48 and title.startswith("这是 第一条 用户消息")
    assert later.json()["data"]["session"]["title"] == title
    assert [item["sequence"] for item in later.json()["data"]["messages"]] == [1, 2, 3]
    assert later.json()["data"]["messages"][1]["metadata"]["toolCallIds"] == ["call-1"]
    assert listed.json()["data"]["sessions"][0]["id"] == session_id
    assert cleared.json()["data"] == {
        "session": cleared.json()["data"]["session"], "messages": []
    }
    assert cleared.json()["data"]["session"]["title"] == "新会话"
    assert restarted.json()["data"]["messages"][0]["sequence"] == 1
    assert restarted.json()["data"]["session"]["title"] == "重新开始"
    assert deleted.json()["data"] == {"deleted": True, "sessionId": session_id}


async def test_chat_owner_scope_and_errors_are_not_enumerable(chat_database_url: str) -> None:
    async with client_for(chat_database_url) as client:
        owner = await _auth(client, "owner@example.com")
        other = await _auth(client, "other@example.com")
        created = await client.post("/chat/sessions", headers=owner)
        session_id = created.json()["data"]["session"]["id"]
        responses = [
            await client.get(f"/chat/sessions/{session_id}", headers=other),
            await client.get("/chat/sessions/missing", headers=other),
            await client.post(
                f"/chat/sessions/{session_id}/messages", headers=other,
                json={"role": "user", "content": "steal"},
            ),
            await client.post(f"/chat/sessions/{session_id}/messages:clear", headers=other),
            await client.delete(f"/chat/sessions/{session_id}", headers=other),
        ]
        unauthenticated = await client.get("/chat/sessions")
        invalid = await client.post(
            f"/chat/sessions/{session_id}/messages", headers=owner,
            json={"role": "invalid", "content": ""},
        )
        owner_detail = await client.get(f"/chat/sessions/{session_id}", headers=owner)

    assert all(response.status_code == 403 for response in responses)
    assert all(response.json()["error"]["code"] == "AUTH_FORBIDDEN" for response in responses)
    assert unauthenticated.status_code == 401
    assert invalid.status_code == 422
    assert owner_detail.status_code == 200


async def test_concurrent_appends_allocate_unique_monotonic_sequences(
    chat_database_url: str,
) -> None:
    async with client_for(chat_database_url) as client:
        headers = await _auth(client, "owner@example.com")
        created = await client.post("/chat/sessions", headers=headers)
        session_id = created.json()["data"]["session"]["id"]
        first, second = await asyncio.gather(
            client.post(
                f"/chat/sessions/{session_id}/messages", headers=headers,
                json={"role": "user", "content": "first"},
            ),
            client.post(
                f"/chat/sessions/{session_id}/messages", headers=headers,
                json={"role": "assistant", "content": "second"},
            ),
        )
        detail = await client.get(f"/chat/sessions/{session_id}", headers=headers)

    assert first.status_code == second.status_code == 200
    assert [message["sequence"] for message in detail.json()["data"]["messages"]] == [1, 2]


async def test_append_rolls_back_message_when_session_touch_fails(
    chat_database_url: str,
) -> None:
    async with client_for(chat_database_url) as client:
        headers = await _auth(client, "owner@example.com")
        created = await client.post("/chat/sessions", headers=headers)
        session_id = created.json()["data"]["session"]["id"]
        engine = create_sqlite_engine(DatabaseSettings(url=chat_database_url))
        try:
            async with engine.begin() as connection:
                await connection.execute(text(
                    "CREATE TRIGGER fail_chat_touch BEFORE UPDATE ON chat_sessions "
                    "BEGIN SELECT RAISE(ABORT, 'touch failed'); END"
                ))
        finally:
            await engine.dispose()

        failed = await client.post(
            f"/chat/sessions/{session_id}/messages", headers=headers,
            json={"role": "user", "content": "must rollback"},
        )
        engine = create_sqlite_engine(DatabaseSettings(url=chat_database_url))
        try:
            async with engine.begin() as connection:
                await connection.execute(text("DROP TRIGGER fail_chat_touch"))
        finally:
            await engine.dispose()
        detail = await client.get(f"/chat/sessions/{session_id}", headers=headers)

    assert failed.status_code == 500
    assert detail.json()["data"]["messages"] == []
    assert detail.json()["data"]["session"]["title"] == "新会话"


async def test_list_uses_id_desc_as_equal_updated_at_tie_breaker(
    chat_database_url: str,
) -> None:
    async with client_for(chat_database_url) as client:
        headers = await _auth(client, "owner@example.com")
        first = await client.post("/chat/sessions", headers=headers)
        second = await client.post("/chat/sessions", headers=headers)
        ids = [first.json()["data"]["session"]["id"], second.json()["data"]["session"]["id"]]
        engine = create_sqlite_engine(DatabaseSettings(url=chat_database_url))
        try:
            async with engine.begin() as connection:
                await connection.execute(text(
                    "UPDATE chat_sessions SET updated_at = '2026-08-17 00:00:00'"
                ))
        finally:
            await engine.dispose()
        listed = await client.get("/chat/sessions", headers=headers)

    assert [item["id"] for item in listed.json()["data"]["sessions"]] == sorted(
        ids, reverse=True
    )


async def test_memory_mode_compact_and_owner_scope(chat_database_url: str) -> None:
    async with client_for(chat_database_url) as client:
        owner = await _auth(client, "owner@example.com")
        other = await _auth(client, "other@example.com")
        created = await client.post("/chat/sessions", headers=owner)
        session_id = created.json()["data"]["session"]["id"]
        empty_compact = await client.post(
            f"/chat/sessions/{session_id}/memory:compact", headers=owner
        )
        updated = await client.put(
            f"/chat/sessions/{session_id}/memory",
            headers=owner,
            json={"memoryMode": "manual"},
        )
        other_session = await client.post("/chat/sessions", headers=owner)
        other_session_id = other_session.json()["data"]["session"]["id"]
        await client.put(
            f"/chat/sessions/{other_session_id}/memory",
            headers=owner,
            json={"memoryMode": "every_30_turns"},
        )
        independently_listed = await client.get("/chat/sessions", headers=owner)
        await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=owner,
            json={"role": "user", "content": "问题"},
        )
        await client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=owner,
            json={"role": "assistant", "content": "回答"},
        )
        compacted = await client.post(
            f"/chat/sessions/{session_id}/memory:compact", headers=owner
        )
        forbidden = await client.put(
            f"/chat/sessions/{session_id}/memory",
            headers=other,
            json={"memoryMode": "every_30_turns"},
        )

    assert empty_compact.status_code == 200
    assert empty_compact.json()["data"]["session"]["canCompact"] is False
    assert updated.json()["data"]["session"]["memoryMode"] == "manual"
    modes = {
        item["id"]: item["memoryMode"]
        for item in independently_listed.json()["data"]["sessions"]
    }
    assert modes == {session_id: "manual", other_session_id: "every_30_turns"}
    assert compacted.json()["data"]["session"]["memorySummary"]
    assert compacted.json()["data"]["session"]["compactedMessageCount"] == 2
    assert len(compacted.json()["data"]["messages"]) == 2
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "AUTH_FORBIDDEN"


async def test_chat_api_fails_explicitly_without_model_capability(chat_database_url: str) -> None:
    await upgrade_database(chat_database_url)
    app = create_app(
        DatabaseSettings(url=chat_database_url),
        worker_settings=WorkerSettings(poll_interval_seconds=60),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            headers = await _auth(client, "missing-capability@example.com")
            response = await client.post("/chat/sessions", headers=headers)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "SYSTEM_MODEL_CAPABILITY_MISSING"
