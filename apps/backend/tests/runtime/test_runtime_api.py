from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import httpx
from _pytest.logging import LogCaptureFixture

from super_ai.app import create_app
from super_ai.runtime.models import (
    RuntimeDependencies,
    RuntimeDependencyName,
    RuntimeDependencyResult,
    RuntimeDependencyStatus,
)


class FakeRuntimeChecks:
    def __init__(self, dependencies: RuntimeDependencies) -> None:
        self.dependencies = dependencies
        self.calls = 0

    async def run(self) -> RuntimeDependencies:
        self.calls += 1
        return self.dependencies

    async def run_mcp(self) -> RuntimeDependencyResult:
        self.calls += 1
        return self.dependencies.mcp


def _dependency(
    name: RuntimeDependencyName,
    status: RuntimeDependencyStatus = "ready",
) -> RuntimeDependencyResult:
    return RuntimeDependencyResult(
        name=name,
        status=status,
        latencyMs=2.5,
        error=None if status == "ready" else "token=secret-value unavailable",
    )


def _dependencies(*, mcp: RuntimeDependencyStatus = "ready") -> RuntimeDependencies:
    return RuntimeDependencies(
        sqlite=_dependency("sqlite"),
        milvus=_dependency("milvus"),
        qwen=_dependency("qwen"),
        mcp=_dependency("mcp", mcp),
    )


async def test_health_never_runs_dependency_checks() -> None:
    checks = FakeRuntimeChecks(_dependencies())
    transport = httpx.ASGITransport(app=create_app(runtime_checks=checks))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert checks.calls == 0


async def test_ready_returns_503_with_all_safe_dependency_results() -> None:
    checks = FakeRuntimeChecks(_dependencies(mcp="unavailable"))
    transport = httpx.ASGITransport(app=create_app(runtime_checks=checks))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready", headers={"X-Request-ID": "req-ready"})
    payload = response.json()
    assert response.status_code == 503
    assert payload["error"]["code"] == "SYSTEM_UNAVAILABLE"
    details = payload["error"]["details"]
    assert details["status"] == "unavailable"
    assert details["dependencies"]["sqlite"]["status"] == "ready"
    assert details["dependencies"]["mcp"]["error"] == "token=[redacted] unavailable"


async def test_ready_returns_200_when_every_dependency_is_ready() -> None:
    checks = FakeRuntimeChecks(_dependencies())
    transport = httpx.ASGITransport(app=create_app(runtime_checks=checks))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ready"


async def test_mcp_health_returns_503_without_configured_source() -> None:
    checks = FakeRuntimeChecks(_dependencies(mcp="unavailable"))
    transport = httpx.ASGITransport(app=create_app(runtime_checks=checks))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/mcp")
    assert response.status_code == 503
    assert response.json()["error"]["details"]["name"] == "mcp"


async def test_config_check_stops_before_dependencies_when_json_is_invalid(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    user = tmp_path / "user.json"
    project.write_text("[]", encoding="utf-8")
    user.write_text("{}", encoding="utf-8")
    checks = FakeRuntimeChecks(_dependencies())
    app = create_app(runtime_checks=checks, project_config_paths=(project, user))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/config/check")
    assert response.status_code == 503
    details = response.json()["error"]["details"]
    assert details["status"] == "configuration_invalid"
    assert details["configuration"]["status"] == "invalid"
    assert details["dependencies"] is None
    assert checks.calls == 0


async def test_config_check_distinguishes_valid_config_from_unreachable_dependency(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[4]
    config = cast(
        dict[str, object],
        json.loads((root / "config/project.template.json").read_text(encoding="utf-8")),
    )
    cast(dict[str, object], config["llm"])["apiKey"] = "test-only-key"
    cast(dict[str, object], config["vectorStore"])["token"] = "test-only-token"
    project = tmp_path / "project.json"
    user = tmp_path / "user.json"
    project.write_text(json.dumps(config), encoding="utf-8")
    user.write_text("{}", encoding="utf-8")
    checks = FakeRuntimeChecks(_dependencies(mcp="unavailable"))
    app = create_app(runtime_checks=checks, project_config_paths=(project, user))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/config/check")
    details = response.json()["error"]["details"]
    assert response.status_code == 503
    assert details["status"] == "dependencies_unavailable"
    assert details["configuration"]["status"] == "valid"
    assert details["dependencies"]["mcp"]["status"] == "unavailable"


async def test_metrics_reports_completed_requests_without_prometheus_text() -> None:
    app = create_app(runtime_checks=FakeRuntimeChecks(_dependencies()))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        await client.get("/missing")
        response = await client.get("/metrics")
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()["data"]
    assert data["scope"] == "process"
    assert data["requestCount"] == 2
    assert data["failureCount"] == 1
    assert data["averageDurationMs"] >= 0


async def test_completion_log_contains_only_allowlisted_fields(
    caplog: LogCaptureFixture,
) -> None:
    app = create_app(runtime_checks=FakeRuntimeChecks(_dependencies()))
    transport = httpx.ASGITransport(app=app)
    with caplog.at_level("INFO", logger="super_ai.http"):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get(
                "/health?token=do-not-log",
                headers={"Authorization": "Bearer do-not-log", "X-Request-ID": "req-log"},
            )
    record = cast(dict[str, object], json.loads(caplog.records[-1].message))
    assert set(record) == {"event", "requestId", "path", "status", "durationMs"}
    assert record["path"] == "/health"
    assert "do-not-log" not in json.dumps(record)
