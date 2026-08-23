from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import scripts.generate_and_upload_cls_logs as cls_script
from scripts.generate_and_upload_cls_logs import (
    ClsLogUploadError,
    ClsLogUploadSettings,
    build_log_group_list,
    generate_log_records,
    load_cls_log_upload_settings,
    upload_logs,
    validate_count,
)

ROOT = Path(__file__).resolve().parents[4]


def _profile_function(name: str) -> Any:
    function = getattr(cls_script, name, None)
    if function is None:
        pytest.fail(f"缺少 profile 行为: {name}")
    return function


def _settings() -> ClsLogUploadSettings:
    return ClsLogUploadSettings(
        endpoint="https://ap-guangzhou.cls.tencentcs.com",
        region="ap-guangzhou",
        logset_id="manual-logset-only",
        topic_id="topic-1",
        secret_id="secret-id-sentinel",
        secret_key="secret-key-sentinel",
    )


@pytest.mark.parametrize("count", [0, -1, 101])
def test_count_is_rejected_before_client_creation(count: int) -> None:
    created = False

    def client_factory(_endpoint: str, _secret_id: str, _secret_key: str) -> _FakeClient:
        nonlocal created
        created = True
        return _FakeClient()

    with pytest.raises(ClsLogUploadError, match="count 必须在 1..100"):
        upload_logs(_settings(), count, client_factory=client_factory)

    assert created is False


def test_generate_three_bounded_records_without_credentials() -> None:
    settings = _settings()
    records = generate_log_records(
        settings,
        3,
        now=datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc),
        trace_id_factory=lambda index: f"trace-{index}",
    )

    assert len(records) == 3
    assert [record["traceId"] for record in records] == ["trace-0", "trace-1", "trace-2"]
    assert all(
        set(record)
        == {"region", "service", "severity", "level", "traceId", "timestamp", "message"}
        for record in records
    )
    assert all(record["region"] == "ap-guangzhou" for record in records)
    assert all(len(record["message"]) <= 240 for record in records)
    serialized = repr(records)
    assert settings.secret_id not in serialized
    assert settings.secret_key not in serialized
    assert "password" not in serialized.casefold()
    assert "token" not in serialized.casefold()


def test_script_loads_recursive_local_json_merge(tmp_path: Path) -> None:
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    project_path.write_text(
        json.dumps(
            {
                "clsLogUpload": {
                    "endpoint": "https://ap-guangzhou.cls.tencentcs.com",
                    "region": "ap-guangzhou",
                    "logsetId": "logset-1",
                    "topicId": "topic-1",
                    "secretId": "",
                    "secretKey": "",
                }
            }
        ),
        encoding="utf-8",
    )
    user_path.write_text(
        json.dumps(
            {
                "clsLogUpload": {
                    "secretId": "secret-id-sentinel",
                    "secretKey": "secret-key-sentinel",
                }
            }
        ),
        encoding="utf-8",
    )

    settings = load_cls_log_upload_settings(project_path, user_path)

    assert settings.endpoint == "https://ap-guangzhou.cls.tencentcs.com"
    assert settings.topic_id == "topic-1"
    assert settings.secret_id == "secret-id-sentinel"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://ap-guangzhou.cls.tencentcs.com",
        "https://user:password@ap-guangzhou.cls.tencentcs.com",
        "https://ap-guangzhou.cls.tencentcs.com/path",
        "https://ap-guangzhou.cls.tencentcs.com?token=secret",
    ],
)
def test_script_rejects_unsafe_endpoint_before_client_creation(endpoint: str) -> None:
    created = False
    settings = _settings()
    settings = ClsLogUploadSettings(
        endpoint=endpoint,
        region=settings.region,
        logset_id=settings.logset_id,
        topic_id=settings.topic_id,
        secret_id=settings.secret_id,
        secret_key=settings.secret_key,
    )

    def client_factory(_endpoint: str, _secret_id: str, _secret_key: str) -> _FakeClient:
        nonlocal created
        created = True
        return _FakeClient()

    with pytest.raises(ClsLogUploadError, match="endpoint 配置无效") as error:
        upload_logs(settings, 1, client_factory=client_factory)

    assert created is False
    assert settings.secret_id not in str(error.value)
    assert settings.secret_key not in str(error.value)


class _FakeResponse:
    def get_request_id(self) -> str:
        return "request-1"


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def put_log_raw(self, topic_id: str, groups: Any) -> _FakeResponse:
        self.calls.append((topic_id, groups))
        return _FakeResponse()


class _Repeated(list[Any]):
    def __init__(self, factory: Any) -> None:
        super().__init__()
        self._factory = factory

    def add(self) -> Any:
        value = self._factory()
        self.append(value)
        return value


class _FakeContent:
    key = ""
    value = ""


class _FakeLog:
    def __init__(self) -> None:
        self.time = 0
        self.contents = _Repeated(_FakeContent)


class _FakeTag:
    key = ""
    value = ""


class _FakeLogGroup:
    def __init__(self) -> None:
        self.filename = ""
        self.source = ""
        self.logTags = _Repeated(_FakeTag)
        self.logs = _Repeated(_FakeLog)


class _FakeLogGroupList:
    def __init__(self) -> None:
        self.logGroupList = _Repeated(_FakeLogGroup)


def _fake_group_builder(records: Any) -> object:
    from unittest.mock import patch

    fake_module = type("FakeClsModule", (), {"LogGroupList": _FakeLogGroupList})
    with patch(
        "scripts.generate_and_upload_cls_logs.importlib.import_module",
        return_value=fake_module,
    ):
        return build_log_group_list(records)


def test_upload_routes_by_endpoint_and_calls_put_log_raw_once() -> None:
    settings = _settings()
    client = _FakeClient()
    factory_args: list[tuple[str, str, str]] = []

    def client_factory(endpoint: str, secret_id: str, secret_key: str) -> _FakeClient:
        factory_args.append((endpoint, secret_id, secret_key))
        return client

    result = upload_logs(
        settings,
        2,
        client_factory=client_factory,
        group_builder=_fake_group_builder,
        now=datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc),
        trace_id_factory=lambda index: f"trace-{index}",
    )

    assert factory_args == [(settings.endpoint, settings.secret_id, settings.secret_key)]
    assert len(client.calls) == 1
    topic_id, groups = client.calls[0]
    assert topic_id == "topic-1"
    assert settings.logset_id not in repr(factory_args)
    assert settings.logset_id not in repr(client.calls)
    assert len(groups.logGroupList) == 1
    assert len(groups.logGroupList[0].logs) == 2
    first_contents = {item.key: item.value for item in groups.logGroupList[0].logs[0].contents}
    assert first_contents["region"] == "ap-guangzhou"
    assert first_contents["traceId"] == "trace-0"
    assert result.count == 2
    assert result.request_id == "request-1"


def test_sdk_exception_redacts_current_credentials() -> None:
    settings = _settings()

    class FailingClient:
        def put_log_raw(self, topic_id: str, groups: object) -> _FakeResponse:
            del topic_id, groups
            raise RuntimeError(f"failed {settings.secret_id} {settings.secret_key}")

    def failing_client_factory(
        _endpoint: str, _secret_id: str, _secret_key: str
    ) -> FailingClient:
        return FailingClient()

    with pytest.raises(ClsLogUploadError) as error:
        upload_logs(
            settings,
            1,
            client_factory=failing_client_factory,
            group_builder=_fake_group_builder,
        )

    assert "[redacted]" in str(error.value)
    assert settings.secret_id not in str(error.value)
    assert settings.secret_key not in str(error.value)


def test_importing_script_does_not_create_client_or_upload(tmp_path: Path) -> None:
    script_path = str(ROOT / "scripts/generate_and_upload_cls_logs.py")
    script = f"""
from unittest.mock import patch
import runpy
with patch('httpx.AsyncClient.__init__', side_effect=AssertionError('http client')):
    runpy.run_path({script_path!r}, run_name='safe_import')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_validate_count_accepts_boundaries() -> None:
    assert validate_count(1) == 1
    assert validate_count(100) == 100


def test_quant_profile_keeps_legacy_default_and_explicit_count() -> None:
    generate_profile_records = _profile_function("generate_profile_records")

    def trace_id(index: int) -> str:
        return f"trace-{index}"

    default_records = generate_profile_records(
        _settings(),
        profile="quant",
        count=None,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        trace_id_factory=trace_id,
    )
    explicit_records = generate_profile_records(
        _settings(),
        profile="quant",
        count=3,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        trace_id_factory=trace_id,
    )

    assert len(default_records) == 20
    assert len(explicit_records) == 3
    assert explicit_records[0]["traceId"] == "trace-0"


def test_java_ecommerce_profile_is_fixed_and_correlated() -> None:
    generate_profile_records = _profile_function("generate_profile_records")
    records = generate_profile_records(
        _settings(),
        profile="java-ecommerce",
        count=None,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )

    assert len(records) == 10
    assert records[0]["incident_id"] == "java-ecom-001-payment-gateway-timeout"
    assert records[0]["service"] == "payment-service"
    assert records[0]["trace_id"] == records[0]["traceId"]
    assert records[0]["alertname"] == "PaymentGatewayTimeoutHigh"
    assert records[0]["sop_id"] == "sop-payment-gateway-timeout"


def test_java_profile_rejects_count_before_client_creation() -> None:
    upload_profile_logs = _profile_function("upload_profile_logs")
    created = False

    def client_factory(_endpoint: str, _secret_id: str, _secret_key: str) -> _FakeClient:
        nonlocal created
        created = True
        return _FakeClient()

    with pytest.raises(ClsLogUploadError, match="java-ecommerce profile 不接受 count"):
        upload_profile_logs(
            _settings(),
            profile="java-ecommerce",
            count=10,
            client_factory=client_factory,
            group_builder=_fake_group_builder,
        )

    assert created is False


def test_java_profile_uploads_one_group_with_ten_records() -> None:
    upload_profile_logs = _profile_function("upload_profile_logs")
    client = _FakeClient()

    def client_factory(_endpoint: str, _secret_id: str, _secret_key: str) -> _FakeClient:
        return client

    result = upload_profile_logs(
        _settings(),
        profile="java-ecommerce",
        count=None,
        client_factory=client_factory,
        group_builder=_fake_group_builder,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )

    assert result.count == 10
    assert len(client.calls) == 1
    _, groups = client.calls[0]
    assert len(groups.logGroupList[0].logs) == 10
