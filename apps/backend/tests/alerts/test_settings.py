from __future__ import annotations

import json
from pathlib import Path

import pytest

from super_ai.alerts.settings import (
    ClsLogUploadSettings,
    load_alert_settings,
    load_cls_log_upload_settings,
)
from super_ai.project_config import ProjectConfigError


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _paths(tmp_path: Path, project: object, user: object | None = None) -> tuple[Path, Path]:
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    _write(project_path, project)
    _write(user_path, {} if user is None else user)
    return project_path, user_path


def test_loads_two_typed_alert_sources_and_user_credentials(tmp_path: Path) -> None:
    project, user = _paths(
        tmp_path,
        {
            "prometheusAlerts": {
                "sources": [
                    {
                        "name": "prometheus-main",
                        "type": "prometheus-v1",
                        "baseUrl": "https://prometheus.example.test",
                        "timeoutSeconds": 8,
                    },
                    {
                        "name": "alertmanager-local",
                        "type": "alertmanager-v2",
                        "baseUrl": "http://127.0.0.1:9093",
                        "timeoutSeconds": 5,
                    },
                ]
            }
        },
        {
            "prometheusAlerts": {
                "sources": [
                    {
                        "name": "prometheus-main",
                        "type": "prometheus-v1",
                        "baseUrl": "https://prometheus.example.test",
                        "timeoutSeconds": 8,
                        "basicAuth": {"username": "reader", "password": "private"},
                    },
                    {
                        "name": "alertmanager-local",
                        "type": "alertmanager-v2",
                        "baseUrl": "http://127.0.0.1:9093",
                        "timeoutSeconds": 5,
                    },
                ]
            }
        },
    )

    settings = load_alert_settings(project, user)

    assert [source.source_type for source in settings.sources] == [
        "prometheus-v1",
        "alertmanager-v2",
    ]
    assert settings.sources[0].basic_auth is not None
    assert settings.sources[0].basic_auth.username == "reader"
    assert settings.sources[0].basic_auth.password == "private"
    assert settings.sources[1].basic_auth is None


@pytest.mark.parametrize(
    "sources",
    [
        [
            {
                "name": "duplicate",
                "type": "prometheus-v1",
                "baseUrl": "https://one.example.test",
                "timeoutSeconds": 5,
            },
            {
                "name": "duplicate",
                "type": "alertmanager-v2",
                "baseUrl": "https://two.example.test",
                "timeoutSeconds": 5,
            },
        ],
        [
            {
                "name": "bad-url",
                "type": "prometheus-v1",
                "baseUrl": "https://user:password@example.test",
                "timeoutSeconds": 5,
            }
        ],
        [
            {
                "name": "bad-timeout",
                "type": "prometheus-v1",
                "baseUrl": "https://example.test",
                "timeoutSeconds": 0,
            }
        ],
        [
            {
                "name": "half-auth",
                "type": "alertmanager-v2",
                "baseUrl": "https://example.test",
                "timeoutSeconds": 5,
                "basicAuth": {"username": "reader", "password": ""},
            }
        ],
        [
            {
                "name": "unknown",
                "type": "custom",
                "baseUrl": "https://example.test",
                "timeoutSeconds": 5,
            }
        ],
    ],
)
def test_rejects_invalid_alert_source_without_echoing_values(
    tmp_path: Path, sources: list[dict[str, object]]
) -> None:
    project, user = _paths(tmp_path, {"prometheusAlerts": {"sources": sources}})

    with pytest.raises(ProjectConfigError, match="prometheusAlerts 配置校验失败") as error:
        load_alert_settings(project, user)

    assert "password" not in str(error.value).casefold()
    assert "reader" not in str(error.value)


def test_cls_placeholders_load_but_upload_readiness_requires_safe_complete_config(
    tmp_path: Path,
) -> None:
    project, user = _paths(
        tmp_path,
        {
            "clsLogUpload": {
                "endpoint": "",
                "region": "",
                "logsetId": "",
                "topicId": "",
                "secretId": "",
                "secretKey": "",
            }
        },
    )

    settings = load_cls_log_upload_settings(project, user)
    assert settings == ClsLogUploadSettings()
    with pytest.raises(ProjectConfigError, match="clsLogUpload 配置不完整"):
        settings.require_upload_ready()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://ap-guangzhou.cls.tencentcs.com",
        "https://user:password@ap-guangzhou.cls.tencentcs.com",
        "https://ap-guangzhou.cls.tencentcs.com/path",
        "https://ap-guangzhou.cls.tencentcs.com?token=bad",
    ],
)
def test_cls_upload_readiness_rejects_unsafe_endpoint(tmp_path: Path, endpoint: str) -> None:
    project, user = _paths(
        tmp_path,
        {
            "clsLogUpload": {
                "endpoint": endpoint,
                "region": "ap-guangzhou",
                "logsetId": "manual-logset",
                "topicId": "topic-1",
                "secretId": "secret-id",
                "secretKey": "secret-key",
            }
        },
    )

    settings = load_cls_log_upload_settings(project, user)
    with pytest.raises(ProjectConfigError, match="clsLogUpload endpoint 配置无效") as error:
        settings.require_upload_ready()

    assert "secret-id" not in str(error.value)
    assert "secret-key" not in str(error.value)
