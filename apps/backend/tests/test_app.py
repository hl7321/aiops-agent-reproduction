import httpx

from super_ai.app import create_app


async def test_health_returns_success_envelope_with_forwarded_request_id() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": "req-health-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-health-1"
    assert response.json() == {
        "ok": True,
        "data": {"status": "ok"},
        "meta": {"requestId": "req-health-1"},
    }


async def test_health_generates_request_id_when_header_is_missing() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    request_id = response.headers["X-Request-ID"]
    assert request_id
    assert response.json()["meta"]["requestId"] == request_id


def test_health_openapi_path_matches_shared_contract() -> None:
    operation = create_app().openapi()["paths"]["/health"]["get"]

    assert operation["operationId"] == "getHealth"
