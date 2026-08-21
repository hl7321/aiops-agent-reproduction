import asyncio
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

import httpx
import pytest

from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import upgrade_database


class DeterministicSummarizer:
    async def summarize(
        self, previous_summary: str | None, messages: Sequence[str]
    ) -> str:
        return f"{previous_summary or ''} {' '.join(messages)}".strip()


@asynccontextmanager
async def feedback_client(url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
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
    login = await client.post(
        "/auth/login", json={"email": email, "password": "correct-password"}
    )
    return {"Authorization": f"Bearer {login.json()['data']['token']}"}


async def _assistant_message(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> tuple[str, str]:
    created = await client.post("/chat/sessions", headers=headers)
    session_id = created.json()["data"]["session"]["id"]
    payload: dict[str, object] = {
        "role": "assistant",
        "content": "带引用的回答",
        "metadata": {
            "references": [{
                "chunkId": "chunk-1", "documentId": "doc-1",
                "knowledgeBaseId": "kb-1", "source": "runbook.md",
                "excerpt": "处置步骤", "metadata": {},
                "vectorRank": 1, "vectorScore": 0.9,
                "bm25Rank": None, "bm25Score": None,
                "rrfScore": 0.01, "rerankRank": 1,
                "rerankScore": 0.95, "score": 0.95,
            }]
        },
    }
    response = await client.post(
        f"/chat/sessions/{session_id}/messages",
        headers=headers,
        json=payload,
    )
    return session_id, response.json()["data"]["messages"][0]["id"]


async def test_feedback_api_upsert_restore_delete_and_owner_scope(
    feedback_database_url: str,
) -> None:
    async with feedback_client(feedback_database_url) as client:
        owner = await _auth(client, "owner@example.com")
        other = await _auth(client, "other@example.com")
        _, message_id = await _assistant_message(client, owner)
        saved = await client.post(
            "/feedback", headers=owner,
            json={
                "targetType": "citation", "targetId": message_id, "subjectId": "chunk-1",
                "rating": "negative", "reason": "  incomplete  ",
                "comment": "  请补充步骤  ", "correction": "  应先检查实例  ",
            },
        )
        restored = await client.get(
            "/feedback", headers=owner,
            params={"targetType": "citation", "targetId": message_id},
        )
        forbidden = await client.get(
            "/feedback", headers=other,
            params={"targetType": "citation", "targetId": message_id},
        )
        deleted = await client.delete(
            f"/feedback/{saved.json()['data']['id']}", headers=owner
        )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["comment"] == "请补充步骤"
    assert saved.json()["data"]["reason"] == "incomplete"
    assert restored.json()["data"]["items"] == [saved.json()["data"]]
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "BUSINESS_RESOURCE_NOT_FOUND"
    assert deleted.json()["data"]["deleted"] is True


async def test_feedback_rejects_unknown_citation_and_invalid_shape(
    feedback_database_url: str,
) -> None:
    async with feedback_client(feedback_database_url) as client:
        owner = await _auth(client, "owner@example.com")
        _, message_id = await _assistant_message(client, owner)
        unknown = await client.post(
            "/feedback", headers=owner,
            json={
                "targetType": "citation", "targetId": message_id,
                "subjectId": "missing", "rating": "negative",
            },
        )
        invalid = await client.post(
            "/feedback", headers=owner,
            json={
                "targetType": "chat_message", "targetId": message_id,
                "subjectId": "chunk-1", "rating": "positive",
            },
        )
    assert unknown.status_code == 404
    assert invalid.status_code == 422


async def test_deleted_parent_is_not_readable_and_body_is_not_logged(
    feedback_database_url: str, caplog: pytest.LogCaptureFixture,
) -> None:
    sentinel = "FEEDBACK_BODY_SENTINEL_9f82"
    async with feedback_client(feedback_database_url) as client:
        owner = await _auth(client, "owner@example.com")
        session_id, message_id = await _assistant_message(client, owner)
        saved = await client.post(
            "/feedback", headers=owner,
            json={
                "targetType": "chat_message", "targetId": message_id,
                "rating": "negative", "comment": sentinel, "correction": sentinel,
            },
        )
        await client.delete(f"/chat/sessions/{session_id}", headers=owner)
        missing = await client.get(
            "/feedback", headers=owner,
            params={"targetType": "chat_message", "targetId": message_id},
        )
    assert saved.status_code == 200
    assert missing.status_code == 404
    assert sentinel not in caplog.text


def test_feedback_openapi_is_authenticated() -> None:
    schema = create_app().openapi()
    assert schema["paths"]["/feedback"]["get"]["security"] == [{"BearerAuth": []}]
    assert schema["paths"]["/feedback"]["post"]["security"] == [{"BearerAuth": []}]
    assert schema["paths"]["/feedback/{id}"]["delete"]["security"] == [{"BearerAuth": []}]


async def test_concurrent_upsert_keeps_one_unique_feedback(
    feedback_database_url: str,
) -> None:
    async with feedback_client(feedback_database_url) as client:
        owner = await _auth(client, "owner@example.com")
        _, message_id = await _assistant_message(client, owner)
        first, second = await asyncio.gather(*[
            client.post(
                "/feedback", headers=owner,
                json={
                    "targetType": "chat_message", "targetId": message_id,
                    "rating": rating,
                },
            )
            for rating in ("positive", "negative")
        ])
        restored = await client.get(
            "/feedback", headers=owner,
            params={"targetType": "chat_message", "targetId": message_id},
        )
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(restored.json()["data"]["items"]) == 1
