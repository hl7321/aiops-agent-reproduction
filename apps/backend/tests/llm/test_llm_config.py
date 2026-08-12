from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest


def _module() -> ModuleType:
    return importlib.import_module("super_ai.llm.config")


def _base_config(api_key: str = "test-api-key") -> dict[str, object]:
    return {
        "llm": {
            "provider": "qwen-openai",
            "apiKey": api_key,
            "baseUrl": "https://dashscope.example/compatible-mode/v1",
            "chat": {
                "model": "qwen3.7-max",
                "temperature": 0.2,
                "timeoutSeconds": 120,
                "maxRetries": 2,
            },
            "embedding": {
                "model": "text-embedding-v4",
                "dimensions": 1024,
                "batchSize": 10,
                "timeoutSeconds": 120,
                "maxRetries": 2,
            },
            "rerank": {
                "model": "qwen3-vl-rerank",
                "endpoint": "https://dashscope.example/api/v1/services/rerank",
                "timeoutSeconds": 120,
                "maxRetries": 2,
            },
        },
        "modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 262144}},
    }


def _write_config_pair(
    tmp_path: Path,
    project: dict[str, object],
    user: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    project_path.write_text(json.dumps(project), encoding="utf-8")
    user_path.write_text(json.dumps(user or {}), encoding="utf-8")
    return project_path, user_path


def test_typed_settings_preserve_defaults_under_nested_user_override(tmp_path: Path) -> None:
    project_path, user_path = _write_config_pair(
        tmp_path,
        _base_config("project-key"),
        {"llm": {"apiKey": "user-key", "chat": {"model": "qwen-next"}}},
    )
    project = json.loads(project_path.read_text(encoding="utf-8"))
    assert isinstance(project, dict)
    project["modelCapabilities"] = {
        "qwen3.7-max": {"contextWindowTokens": 262144},
        "qwen-next": {"contextWindowTokens": 131072},
    }
    project_path.write_text(json.dumps(project), encoding="utf-8")

    settings = _module().load_llm_settings(project_path, user_path)

    assert settings.api_key.get_secret_value() == "user-key"
    assert settings.chat.model == "qwen-next"
    assert settings.chat.temperature == 0.2
    assert settings.chat.timeout_seconds == 120.0
    assert settings.capability_for_chat().context_window_tokens == 131072


@pytest.mark.parametrize(
    ("case", "expected_path"),
    [
        ("missing-embedding", "llm.embedding"),
        ("invalid-rerank-url", "llm.rerank.endpoint"),
        ("oversized-batch", "llm.embedding.batchSize"),
        ("missing-capability", "modelCapabilities"),
    ],
)
def test_invalid_llm_config_reports_safe_field_path(
    tmp_path: Path,
    case: str,
    expected_path: str,
) -> None:
    config = _base_config("SENTINEL_TYPED_CONFIG_KEY")
    llm = cast(dict[str, Any], config["llm"])
    if case == "missing-embedding":
        llm.pop("embedding")
    elif case == "invalid-rerank-url":
        cast(dict[str, Any], llm["rerank"])["endpoint"] = "ftp://unsafe"
    elif case == "oversized-batch":
        cast(dict[str, Any], llm["embedding"])["batchSize"] = 11
    else:
        config["modelCapabilities"] = {}
    project_path, user_path = _write_config_pair(tmp_path, config)

    with pytest.raises(ValueError) as captured:
        _module().load_llm_settings(project_path, user_path)

    assert type(captured.value).__name__ == "ModelConfigurationError"
    assert expected_path in str(captured.value)
    assert "SENTINEL_TYPED_CONFIG_KEY" not in str(captured.value)


def test_empty_json_api_key_never_falls_back_to_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "SENTINEL_ENVIRONMENT_KEY")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "SENTINEL_DASHSCOPE_KEY")
    project_path, user_path = _write_config_pair(tmp_path, _base_config(api_key=""))

    settings = _module().load_llm_settings(project_path, user_path)

    with pytest.raises(ValueError) as captured:
        settings.require_api_key()
    assert "本地 JSON" in str(captured.value)
    assert "SENTINEL" not in str(captured.value)


def test_template_defaults_define_locked_qwen_profiles() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    settings = _module().load_llm_settings(
        repository_root / "config/project.template.json",
        repository_root / "config/user.project.template.json",
    )

    assert settings.chat.model == "qwen3.7-max"
    assert settings.chat.temperature == 0.2
    assert settings.chat.timeout_seconds == 120.0
    assert settings.chat.max_retries == 2
    assert settings.embedding.model == "text-embedding-v4"
    assert settings.embedding.dimensions == 1024
    assert settings.embedding.batch_size == 10
    assert settings.rerank.model == "qwen3-vl-rerank"
    assert settings.capability_for_chat().context_window_tokens == 262144
