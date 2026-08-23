from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]


def _no_sleep(_seconds: float) -> None:
    return None


def _seeder() -> ModuleType:
    try:
        return importlib.import_module("scripts.seed_java_ecommerce_aiops_sops")
    except ModuleNotFoundError:
        pytest.fail("缺少 Java 电商 SOP seed 脚本")


class _FakeTransport:
    def __init__(self, *, task_status: str = "succeeded") -> None:
        self.task_status = task_status
        self.calls: list[dict[str, Any]] = []
        self.upload_count = 0
        self.task_count = 0

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> Any:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
                "timeout": timeout_seconds,
            }
        )
        if url.endswith("/auth/login"):
            return _response(200, {"user": {"id": "user-1"}, "token": "raw-token"})
        if url.endswith("/knowledge-bases"):
            return _response(200, {"items": [{"id": "kb-user-1"}]})
        if url.endswith("/documents"):
            self.upload_count += 1
            return _response(201, {"id": f"doc-{self.upload_count}"})
        if url.endswith("/index-tasks"):
            self.task_count += 1
            return _response(
                201,
                {"id": f"task-{self.task_count}", "status": "pending"},
            )
        if "/index-tasks/task-" in url:
            task_id = url.rsplit("/", 1)[-1]
            return _response(200, {"id": task_id, "status": self.task_status})
        raise AssertionError(f"unexpected request: {method} {url}")


def _response(status: int, data: object) -> Any:
    body = json.dumps({"ok": True, "data": data, "meta": {"requestId": "req-1"}}).encode()
    return type("Response", (), {"status": status, "body": body})()


def _settings(module: ModuleType) -> Any:
    return module.AiopsDemoSettings(
        backend_base_url="http://127.0.0.1:8000",
        email="demo@example.com",
        password="password-sentinel",
        poll_interval_seconds=0.1,
        index_wait_seconds=30,
    )


def test_loads_aiops_demo_from_recursive_local_json_merge(tmp_path: Path) -> None:
    module = _seeder()
    project = tmp_path / "project.json"
    user = tmp_path / "user.project.json"
    project.write_text(
        json.dumps(
            {
                "aiopsDemo": {
                    "backendBaseUrl": "http://127.0.0.1:8000",
                    "email": "",
                    "password": "",
                    "pollIntervalSeconds": 2,
                    "indexWaitSeconds": 120,
                }
            }
        ),
        encoding="utf-8",
    )
    user.write_text(
        json.dumps(
            {
                "aiopsDemo": {
                    "email": "demo@example.com",
                    "password": "password-sentinel",
                }
            }
        ),
        encoding="utf-8",
    )

    settings = module.load_aiops_demo_settings(project, user)

    assert settings.backend_base_url == "http://127.0.0.1:8000"
    assert settings.email == "demo@example.com"
    assert settings.password == "password-sentinel"
    assert settings.poll_interval_seconds == 2
    assert settings.index_wait_seconds == 120


def test_seeds_ten_markdown_sops_and_waits_for_durable_indexing() -> None:
    module = _seeder()
    transport = _FakeTransport()

    result = module.seed_java_sops(
        _settings(module),
        confirmed=True,
        transport=transport,
        sleep=_no_sleep,
    )

    assert result.uploaded == result.indexed == 10
    assert result.knowledge_base_id == "kb-user-1"
    assert len(transport.calls) == 32
    login_call = transport.calls[0]
    assert json.loads(login_call["body"]) == {
        "email": "demo@example.com",
        "password": "password-sentinel",
    }
    protected_calls = transport.calls[1:]
    assert all(call["headers"]["Authorization"] == "Bearer raw-token" for call in protected_calls)
    uploads = [call for call in transport.calls if call["url"].endswith("/documents")]
    assert len(uploads) == 10
    for upload in uploads:
        content_type = upload["headers"]["Content-Type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        body = upload["body"].decode("utf-8")
        assert 'name="file"' in body
        assert "Content-Type: text/markdown" in body
        assert 'name="chunkingConfig"' in body
        assert '"strategy":"fixed-character"' in body
        assert "knowledgeType: aiops-sop" in body


def test_failed_index_task_exits_with_incident_and_without_password() -> None:
    module = _seeder()
    transport = _FakeTransport(task_status="failed")

    with pytest.raises(module.SopSeedError) as error:
        module.seed_java_sops(
            _settings(module),
            confirmed=True,
            transport=transport,
            sleep=_no_sleep,
        )

    message = str(error.value)
    assert "java-ecom-001-payment-gateway-timeout" in message
    assert "索引失败" in message
    assert "password-sentinel" not in message
    assert "全部成功" not in message


def test_timeout_does_not_claim_success() -> None:
    module = _seeder()
    transport = _FakeTransport(task_status="running")
    ticks = iter((0.0, 31.0))

    with pytest.raises(module.SopSeedError, match="索引等待超时") as error:
        module.seed_java_sops(
            _settings(module),
            confirmed=True,
            transport=transport,
            sleep=_no_sleep,
            monotonic=lambda: next(ticks),
        )

    assert "全部成功" not in str(error.value)


def test_confirmation_is_required_before_transport() -> None:
    module = _seeder()
    transport = _FakeTransport()

    with pytest.raises(module.SopSeedError, match="必须显式确认"):
        module.seed_java_sops(
            _settings(module),
            confirmed=False,
            transport=transport,
        )

    assert transport.calls == []


def test_api_failure_does_not_echo_response_or_password() -> None:
    module = _seeder()

    class FailingTransport:
        def request(self, *args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            body = b'{"error":{"message":"password-sentinel token=unsafe"}}'
            return type("Response", (), {"status": 401, "body": body})()

    with pytest.raises(module.SopSeedError) as error:
        module.seed_java_sops(
            _settings(module),
            confirmed=True,
            transport=FailingTransport(),
        )

    assert "HTTP 401" in str(error.value)
    assert "password-sentinel" not in str(error.value)
    assert "token=unsafe" not in str(error.value)


def test_import_has_no_config_or_network_side_effect() -> None:
    script_path = str(ROOT / "scripts/seed_java_ecommerce_aiops_sops.py")
    script = f"""
from unittest.mock import patch
import runpy
with patch('pathlib.Path.read_text', side_effect=AssertionError('config')):
    with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
        runpy.run_path({script_path!r}, run_name='safe_import')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
