from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx

from super_ai.app import create_app
from super_ai.background_jobs.runtime import WorkerSettings
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import upgrade_database


@asynccontextmanager
async def client_for(url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    await upgrade_database(url)
    app = create_app(
        DatabaseSettings(url=url), worker_settings=WorkerSettings(poll_interval_seconds=60)
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


async def _auth(client: httpx.AsyncClient, email: str) -> str:
    await client.post("/auth/register", json={"email": email, "password": "correct-password"})
    response = await client.post(
        "/auth/login", json={"email": email, "password": "correct-password"}
    )
    return response.json()["data"]["token"]


async def test_knowledge_api_upload_preview_conflict_overwrite_delete(
    knowledge_database_url: str,
) -> None:
    async with client_for(knowledge_database_url) as client:
        token = await _auth(client, "owner@example.com")
        headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req-knowledge"}
        bases = await client.get("/knowledge-bases", headers=headers)
        kb = bases.json()["data"]["items"][0]["id"]
        files = {"file": ("guide.md", "# A\n" + "x" * 500, "text/markdown")}
        data = {"chunkingConfig": '{"strategy":"paragraph"}'}
        uploaded = await client.post(
            f"/knowledge-bases/{kb}/documents", files=files, data=data, headers=headers
        )
        document = uploaded.json()["data"]
        duplicate = await client.post(
            f"/knowledge-bases/{kb}/documents", files=files, data=data, headers=headers
        )
        overwritten = await client.post(
            f"/knowledge-bases/{kb}/documents",
            files=files,
            data={**data, "overwrite": "true"},
            headers=headers,
        )
        current_document = await client.get(
            f"/knowledge-bases/{kb}/documents/{overwritten.json()['data']['id']}",
            headers=headers,
        )
        listed = await client.get(f"/knowledge-bases/{kb}/documents", headers=headers)
        preview = await client.get(
            f"/knowledge-bases/{kb}/documents/{overwritten.json()['data']['id']}/chunk-preview",
            headers=headers,
        )
        deleted = await client.delete(
            f"/knowledge-bases/{kb}/documents/{overwritten.json()['data']['id']}", headers=headers
        )
        missing = await client.get(
            f"/knowledge-bases/{kb}/documents/{document['id']}", headers=headers
        )

    assert bases.headers["X-Request-ID"] == "req-knowledge"
    assert uploaded.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "BUSINESS_CONFLICT"
    assert overwritten.status_code == 201
    assert current_document.status_code == 200
    assert current_document.json()["data"]["chunkingConfig"] == {"strategy": "paragraph"}
    assert "indexableText" not in current_document.json()["data"]
    assert len(listed.json()["data"]["items"]) == 1
    assert preview.json()["data"]["items"][0]["excerpt"].startswith("# A")
    assert deleted.status_code == 200
    assert missing.status_code == 404


async def test_knowledge_api_rejects_other_kb_and_invalid_upload(
    knowledge_database_url: str,
) -> None:
    async with client_for(knowledge_database_url) as client:
        token = await _auth(client, "owner@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        forbidden = await client.get("/knowledge-bases/kb_other/documents", headers=headers)
        invalid = await client.post(
            "/knowledge-bases/kb_other/documents",
            files={"file": ("bad.txt", "bad", "text/plain")},
            headers=headers,
        )
        unauthenticated = await client.get("/knowledge-bases")
        bases = await client.get("/knowledge-bases", headers=headers)
        kb = bases.json()["data"]["items"][0]["id"]
        bad_config = await client.post(
            f"/knowledge-bases/{kb}/documents",
            files={"file": ("valid.md", "text", "text/markdown")},
            data={
                "chunkingConfig": '{"strategy":"fixed-character","maxCharacters":10,"overlap":10}'
            },
            headers=headers,
        )
    assert forbidden.status_code == invalid.status_code == 403
    assert unauthenticated.status_code == 401
    assert bad_config.status_code == 422
    assert bad_config.json()["error"]["details"]["fields"][0]["path"].startswith(
        "body.chunkingConfig"
    )


async def test_two_users_cannot_access_each_others_default_knowledge_base(
    knowledge_database_url: str,
) -> None:
    async with client_for(knowledge_database_url) as client:
        owner_token = await _auth(client, "owner@example.com")
        other_token = await _auth(client, "other@example.com")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        other_headers = {"Authorization": f"Bearer {other_token}"}
        owner_bases = await client.get("/knowledge-bases", headers=owner_headers)
        owner_kb = owner_bases.json()["data"]["items"][0]["id"]
        uploaded = await client.post(
            f"/knowledge-bases/{owner_kb}/documents",
            files={"file": ("private.md", "私有内容", "text/markdown")},
            headers=owner_headers,
        )
        document_id = uploaded.json()["data"]["id"]

        list_forbidden = await client.get(
            f"/knowledge-bases/{owner_kb}/documents", headers=other_headers
        )
        detail_forbidden = await client.get(
            f"/knowledge-bases/{owner_kb}/documents/{document_id}", headers=other_headers
        )
        delete_forbidden = await client.delete(
            f"/knowledge-bases/{owner_kb}/documents/{document_id}", headers=other_headers
        )

    assert uploaded.status_code == 201
    assert list_forbidden.status_code == 403
    assert detail_forbidden.status_code == 403
    assert delete_forbidden.status_code == 403
    assert all(
        response.json()["error"]["code"] == "AUTH_FORBIDDEN"
        for response in (list_forbidden, detail_forbidden, delete_forbidden)
    )
