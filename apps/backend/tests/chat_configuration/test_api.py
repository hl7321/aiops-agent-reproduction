from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx

from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import upgrade_database


@asynccontextmanager
async def _client(url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url), worker_settings=WorkerSettings(poll_interval_seconds=60)
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


async def test_prompt_skill_configuration_lifecycle(chat_configuration_database_url: str) -> None:
    async with _client(chat_configuration_database_url) as client:
        headers = await _auth(client, "owner@example.com")
        empty = await client.get("/chat/configuration", headers=headers)
        prompt = await client.post(
            "/chat/prompts", headers=headers, json={"label": "值班", "content": "回答简洁"}
        )
        uploaded = await client.post(
            "/chat/skills",
            headers=headers,
            files={
                "file": (
                    "SKILL.md",
                    b"---\nname: Log Analysis\ndescription: Analyze logs.\n---\nSteps",
                    "text/markdown",
                )
            },
        )
        prompt_id = prompt.json()["data"]["prompts"][0]["id"]
        skill_id = uploaded.json()["data"]["skills"][0]["id"]
        selected = await client.put(
            "/chat/configuration",
            headers=headers,
            json={"selectedPromptId": prompt_id, "selectedSkillIds": [skill_id, skill_id]},
        )
        invalid = await client.put(
            "/chat/configuration",
            headers=headers,
            json={"selectedPromptId": prompt_id, "selectedSkillIds": [skill_id, "missing"]},
        )
        after_invalid = await client.get("/chat/configuration", headers=headers)
        removed = await client.delete(f"/chat/prompts/{prompt_id}", headers=headers)
        after_delete = await client.get("/chat/configuration", headers=headers)

    assert empty.json()["data"] == {
        "prompts": [],
        "skills": [],
        "selectedPromptId": None,
        "selectedSkillIds": [],
    }
    assert selected.json()["data"]["selectedSkillIds"] == [skill_id]
    assert invalid.status_code == 404
    assert after_invalid.json()["data"]["selectedPromptId"] == prompt_id
    assert after_invalid.json()["data"]["selectedSkillIds"] == [skill_id]
    assert removed.json()["data"] == {"deleted": True, "assetId": prompt_id}
    assert removed.status_code == 200
    assert after_delete.json()["data"]["selectedPromptId"] is None


async def test_configuration_rejects_cross_owner_and_duplicate_skill(
    chat_configuration_database_url: str,
) -> None:
    async with _client(chat_configuration_database_url) as client:
        owner = await _auth(client, "owner@example.com")
        other = await _auth(client, "other@example.com")
        prompt = await client.post(
            "/chat/prompts", headers=owner, json={"label": "owner", "content": "only owner"}
        )
        prompt_id = prompt.json()["data"]["prompts"][0]["id"]
        denied = await client.put(
            "/chat/configuration",
            headers=other,
            json={"selectedPromptId": prompt_id, "selectedSkillIds": []},
        )
        body = b"---\nname: Same_Name\ndescription: Same.\n---\nbody"
        first = await client.post("/chat/skills", headers=owner, files={"file": ("SKILL.md", body)})
        duplicate = await client.post(
            "/chat/skills", headers=owner, files={"file": ("SKILL.md", body)}
        )
        other_same_name = await client.post(
            "/chat/skills", headers=other, files={"file": ("SKILL.md", body)}
        )
        unauthenticated = await client.get("/chat/configuration")

    assert denied.status_code == 404
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert other_same_name.status_code == 201
    assert unauthenticated.status_code == 401
