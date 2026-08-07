from typing import NoReturn

import httpx
from fastapi import FastAPI, Request

from super_ai.api_responses import AppError, success_response
from super_ai.app import create_app


async def business_error() -> NoReturn:
    raise AppError("BUSINESS_RULE_VIOLATION")


async def validation(request: Request, limit: int) -> object:
    return success_response({"limit": limit}, request.state.request_id)


async def crash() -> NoReturn:
    raise RuntimeError("INTERNAL_SENTINEL_MUST_NOT_LEAK")


def create_contract_test_app() -> FastAPI:
    app = create_app()
    app.add_api_route("/_test/business", business_error, methods=["GET"], response_model=None)
    app.add_api_route("/_test/validation", validation, methods=["GET"])
    app.add_api_route("/_test/crash", crash, methods=["GET"], response_model=None)

    return app


async def test_registered_business_error_uses_catalog_and_request_id() -> None:
    transport = httpx.ASGITransport(app=create_contract_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/_test/business",
            headers={"X-Request-ID": "req-business-1"},
        )

    assert response.status_code == 409
    assert response.headers["X-Request-ID"] == "req-business-1"
    assert response.json() == {
        "ok": False,
        "error": {
            "code": "BUSINESS_RULE_VIOLATION",
            "category": "business",
            "httpStatus": 409,
            "message": "请求与当前业务规则冲突",
        },
        "meta": {"requestId": "req-business-1"},
    }


async def test_validation_error_has_safe_field_path_and_generated_request_id() -> None:
    transport = httpx.ASGITransport(app=create_contract_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test/validation", params={"limit": "not-an-int"})

    payload = response.json()
    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 422
    assert payload["meta"]["requestId"] == request_id
    assert payload["error"]["code"] == "VALIDATION_REQUEST_INVALID"
    assert payload["error"]["category"] == "validation"
    assert payload["error"]["httpStatus"] == 422
    assert payload["error"]["details"]["fields"] == [
        {
            "path": "query.limit",
            "type": "int_parsing",
            "message": "Input should be a valid integer, unable to parse string as an integer",
        }
    ]


async def test_unhandled_exception_uses_safe_system_error() -> None:
    transport = httpx.ASGITransport(app=create_contract_test_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/_test/crash",
            headers={"X-Request-ID": "req-system-1"},
        )

    payload = response.json()
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "req-system-1"
    assert payload == {
        "ok": False,
        "error": {
            "code": "SYSTEM_INTERNAL_ERROR",
            "category": "system",
            "httpStatus": 500,
            "message": "服务暂时不可用",
        },
        "meta": {"requestId": "req-system-1"},
    }
    assert "INTERNAL_SENTINEL_MUST_NOT_LEAK" not in response.text


async def test_invalid_request_id_is_replaced() -> None:
    transport = httpx.ASGITransport(app=create_contract_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": "contains spaces"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "contains spaces"
    assert response.json()["meta"]["requestId"] == response.headers["X-Request-ID"]


async def test_framework_404_and_405_use_registered_failure_envelopes() -> None:
    transport = httpx.ASGITransport(app=create_contract_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        not_found = await client.get("/missing", headers={"X-Request-ID": "req-404"})
        method_not_allowed = await client.post(
            "/health",
            headers={"X-Request-ID": "req-405"},
        )

    assert not_found.status_code == 404
    assert not_found.json() == {
        "ok": False,
        "error": {
            "code": "SYSTEM_ROUTE_NOT_FOUND",
            "category": "system",
            "httpStatus": 404,
            "message": "请求的资源不存在",
        },
        "meta": {"requestId": "req-404"},
    }
    assert method_not_allowed.status_code == 405
    assert method_not_allowed.json() == {
        "ok": False,
        "error": {
            "code": "SYSTEM_METHOD_NOT_ALLOWED",
            "category": "system",
            "httpStatus": 405,
            "message": "请求方法不受支持",
        },
        "meta": {"requestId": "req-405"},
    }
