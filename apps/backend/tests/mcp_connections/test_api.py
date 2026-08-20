from pathlib import Path

import httpx
from langchain_core.tools import tool

from super_ai.api_responses import AppError
from super_ai.app import create_app
from super_ai.mcp_connections.gateway import McpToolSet
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import upgrade_database


@tool
def query_logs(query: str) -> str:
    """查询真实日志。"""
    return query


class FakeGateway:
    async def discover(self, targets: object, *, builtin_tool_names: frozenset[str]) -> McpToolSet:
        del targets, builtin_tool_names
        return McpToolSet((query_logs,), frozenset({"query_logs"}))


class FailingGateway:
    async def discover(
        self, targets: object, *, builtin_tool_names: frozenset[str]
    ) -> McpToolSet:
        del targets, builtin_tool_names
        raise AppError("SYSTEM_MCP_CONNECTION_FAILED", message="MCP_FAILURE_SENTINEL")


class InvalidCatalogGateway:
    async def discover(self, targets: object, *, builtin_tool_names: frozenset[str]) -> McpToolSet:
        del targets, builtin_tool_names
        invalid = query_logs.model_copy(update={"description": "x" * 2001})
        return McpToolSet((invalid,), frozenset({"query_logs"}))


async def _register(client: httpx.AsyncClient, email: str) -> str:
    response = await client.post(
        "/auth/register", json={"email": email, "password": "secure-password"}
    )
    assert response.status_code == 201
    login = await client.post("/auth/login", json={"email": email, "password": "secure-password"})
    assert login.status_code == 200
    return str(login.json()["data"]["token"])


async def test_mcp_crud_check_and_owner_scope(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'api.sqlite3'}"
    await upgrade_database(url)
    app = create_app(DatabaseSettings(url=url), mcp_gateway=FakeGateway())
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            token_a = await _register(client, "a@example.com")
            token_b = await _register(client, "b@example.com")
            headers_a = {"Authorization": f"Bearer {token_a}"}
            created = await client.post(
                "/mcp/connections",
                headers=headers_a,
                json={
                    "name": "CLS",
                    "transport": "streamable_http",
                    "url": "https://example.test/mcp?mode=read",
                    "enabled": True,
                    "timeoutSeconds": 30,
                    "retries": 1,
                },
            )
            assert created.status_code == 201
            connection_id = created.json()["data"]["id"]
            assert created.json()["data"]["url"].endswith("?mode=read")
            duplicate = await client.post(
                "/mcp/connections",
                headers=headers_a,
                json={
                    "name": "CLS",
                    "transport": "sse",
                    "url": "https://other.example.test/sse",
                    "enabled": True,
                    "timeoutSeconds": 10,
                    "retries": 0,
                },
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "BUSINESS_CONFLICT"

            checked = await client.post(
                f"/mcp/connections/{connection_id}:check", headers=headers_a
            )
            assert checked.status_code == 200
            assert checked.json()["data"]["status"] == "connected"
            assert checked.json()["data"]["tools"] == [
                {"name": "query_logs", "description": "查询真实日志。"}
            ]

            app.state.mcp_gateway = FailingGateway()
            failed = await client.post(
                f"/mcp/connections/{connection_id}:check", headers=headers_a
            )
            assert failed.status_code == 200
            assert failed.json()["data"]["status"] == "failed"
            assert failed.json()["data"]["tools"] == []
            assert "MCP_FAILURE_SENTINEL" not in failed.text

            app.state.mcp_gateway = InvalidCatalogGateway()
            invalid_catalog = await client.post(
                f"/mcp/connections/{connection_id}:check", headers=headers_a
            )
            assert invalid_catalog.status_code == 200
            assert invalid_catalog.json()["data"]["status"] == "failed"
            assert invalid_catalog.json()["data"]["tools"] == []
            assert "x" * 2001 not in invalid_catalog.text

            listed = await client.get("/mcp/connections", headers=headers_a)
            discovered = listed.json()["data"]["connections"][0]["discoveredTools"]
            assert discovered == []

            forbidden = await client.delete(
                f"/mcp/connections/{connection_id}",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert forbidden.status_code == 404
            assert forbidden.json()["error"]["code"] == "BUSINESS_RESOURCE_NOT_FOUND"

            deleted = await client.delete(f"/mcp/connections/{connection_id}", headers=headers_a)
            assert deleted.status_code == 200
            assert deleted.json()["data"] == {"deleted": True, "connectionId": connection_id}


async def test_mcp_rejects_userinfo_without_echoing_credentials(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'unsafe.sqlite3'}"
    await upgrade_database(url)
    app = create_app(DatabaseSettings(url=url), mcp_gateway=FakeGateway())
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            token = await _register(client, "safe@example.com")
            response = await client.post(
                "/mcp/connections",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": "unsafe",
                    "transport": "sse",
                    "url": "https://user:password@example.test/sse",
                    "enabled": True,
                    "timeoutSeconds": 30,
                    "retries": 0,
                },
            )
    assert response.status_code == 422
    assert "user:password" not in response.text


def test_mcp_openapi_responses_match_each_operation_error_catalog() -> None:
    schema = create_app().openapi()

    assert set(schema["paths"]["/mcp/connections"]["get"]["responses"]) == {"200", "401", "403"}
    assert set(schema["paths"]["/mcp/connections"]["post"]["responses"]) == {
        "201", "401", "403", "409", "422"
    }
    assert set(schema["paths"]["/mcp/connections/{id}"]["put"]["responses"]) == {
        "200", "401", "403", "404", "409", "422"
    }
    assert set(schema["paths"]["/mcp/connections/{id}"]["delete"]["responses"]) == {
        "200", "401", "403", "404", "422"
    }
    assert set(schema["paths"]["/mcp/connections/{id}:check"]["post"]["responses"]) == {
        "200", "401", "403", "404", "422", "502"
    }
