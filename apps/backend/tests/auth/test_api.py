from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx

from super_ai.app import create_app
from super_ai.memory.config import DatabaseSettings
from super_ai.memory.sqlite import upgrade_database


@asynccontextmanager
async def auth_client(database_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    await upgrade_database(database_url)
    app = create_app(DatabaseSettings(url=database_url))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


async def test_register_login_me_logout_full_flow(auth_database_url: str) -> None:
    async with auth_client(auth_database_url) as client:
        registered = await client.post(
            "/auth/register",
            json={"email": " User@Example.COM ", "password": "correct horse battery staple"},
            headers={"X-Request-ID": "req-register"},
        )
        duplicate = await client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "another password"},
        )
        assert registered.status_code == 201, registered.text
        assert duplicate.status_code == 409, duplicate.text
        login = await client.post(
            "/auth/login",
            json={"email": "USER@example.com", "password": "correct horse battery staple"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["data"]["token"]
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        logout = await client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        revoked = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        second_login = await client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "correct horse battery staple"},
        )
        second_token = second_login.json()["data"]["token"]
        restored = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {second_token}"}
        )

    assert registered.status_code == 201
    assert registered.headers["X-Request-ID"] == "req-register"
    assert registered.json() == {
        "ok": True,
        "data": {
            "id": registered.json()["data"]["id"],
            "email": "user@example.com",
            "createdAt": registered.json()["data"]["createdAt"],
        },
        "meta": {"requestId": "req-register"},
    }
    assert "password" not in registered.text
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "AUTH_EMAIL_ALREADY_REGISTERED"
    assert login.status_code == 200
    assert me.json()["data"] == registered.json()["data"]
    assert logout.json()["data"] == {"revoked": True}
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "AUTH_REQUIRED"
    assert second_login.status_code == 200
    assert second_token != token
    assert restored.json()["data"] == registered.json()["data"]


async def test_wrong_and_unknown_credentials_return_identical_error(auth_database_url: str) -> None:
    async with auth_client(auth_database_url) as client:
        await client.post(
            "/auth/register", json={"email": "user@example.com", "password": "correct"}
        )
        wrong = await client.post(
            "/auth/login", json={"email": "user@example.com", "password": "wrong"}
        )
        unknown = await client.post(
            "/auth/login", json={"email": "missing@example.com", "password": "wrong"}
        )

    assert wrong.status_code == unknown.status_code == 401
    for response in (wrong, unknown):
        payload = response.json()
        assert payload["error"] == {
            "code": "AUTH_INVALID_CREDENTIALS",
            "category": "authentication",
            "httpStatus": 401,
            "message": "邮箱或密码错误",
        }


async def test_auth_validation_missing_bearer_and_cors(auth_database_url: str) -> None:
    async with auth_client(auth_database_url) as client:
        validation = await client.post(
            "/auth/register", json={"email": "not-an-email", "password": "short"}
        )
        missing = await client.get("/auth/me")
        preflight = await client.options(
            "/auth/login",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type,x-request-id",
            },
        )

    assert validation.status_code == 422
    assert validation.json()["error"]["details"]["fields"][0]["path"].startswith("body.")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTH_REQUIRED"
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "authorization" in preflight.headers["access-control-allow-headers"].lower()


def test_auth_openapi_paths_and_bearer_scheme() -> None:
    schema = create_app().openapi()
    assert schema["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert schema["paths"]["/auth/register"]["post"]["operationId"] == "registerUser"
    assert schema["paths"]["/auth/login"]["post"]["operationId"] == "loginUser"
    assert schema["paths"]["/auth/logout"]["post"]["security"] == [{"BearerAuth": []}]
    assert schema["paths"]["/auth/me"]["get"]["security"] == [{"BearerAuth": []}]
