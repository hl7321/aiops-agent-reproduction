from __future__ import annotations

import json
from pathlib import Path

import pytest

from super_ai.vector_store.config import load_vector_store_settings
from super_ai.vector_store.errors import VectorStoreConfigurationError


def _write_config(path: Path, vector_store: object) -> None:
    path.write_text(json.dumps({"vectorStore": vector_store}), encoding="utf-8")


def test_load_settings_uses_recursive_json_merge(tmp_path: Path) -> None:
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    _write_config(
        project_path,
        {
            "uri": "http://127.0.0.1:19530",
            "token": "project-token",
            "collectionName": "super_ai_chunks",
        },
    )
    _write_config(user_path, {"token": "user-token"})

    settings = load_vector_store_settings(project_path, user_path)

    assert settings.uri == "http://127.0.0.1:19530"
    assert settings.token.get_secret_value() == "user-token"
    assert settings.collection_name == "super_ai_chunks"


@pytest.mark.parametrize(
    ("vector_store", "path"),
    [
        ({"token": "secret", "collectionName": "chunks"}, "vectorStore.uri"),
        (
            {"uri": "grpc://localhost:19530", "token": "secret", "collectionName": "chunks"},
            "vectorStore.uri",
        ),
        (
            {"uri": "http://localhost:19530", "token": "secret", "collectionName": "bad-name"},
            "vectorStore.collectionName",
        ),
        (
            {"uri": "http://localhost:19530", "token": "", "collectionName": "chunks"},
            "vectorStore.token",
        ),
    ],
)
def test_invalid_settings_fail_with_safe_field_path(
    tmp_path: Path,
    vector_store: object,
    path: str,
) -> None:
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    _write_config(project_path, vector_store)
    user_path.write_text("{}", encoding="utf-8")

    with pytest.raises(VectorStoreConfigurationError) as captured:
        load_vector_store_settings(project_path, user_path)

    assert path in str(captured.value)
    assert "secret" not in str(captured.value)


def test_environment_cannot_supply_missing_vector_store_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MILVUS_URI", "http://environment.example:19530")
    monkeypatch.setenv("MILVUS_TOKEN", "environment-secret")
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    _write_config(project_path, {"collectionName": "chunks"})
    user_path.write_text("{}", encoding="utf-8")

    with pytest.raises(VectorStoreConfigurationError) as captured:
        load_vector_store_settings(project_path, user_path)

    message = str(captured.value)
    assert "vectorStore.uri" in message
    assert "vectorStore.token" in message
    assert "environment-secret" not in message
