import json
from pathlib import Path

import pytest

import super_ai.project_config as project_config
from super_ai.project_config import JsonObject, deep_merge, load_project_config


def test_deep_merge_preserves_nested_defaults() -> None:
    base: JsonObject = {
        "frontend": {"title": "基础标题", "apiBaseUrl": "/api"},
        "features": ["a"],
    }
    override: JsonObject = {"frontend": {"title": "本机标题"}, "features": ["b"]}

    assert deep_merge(base, override) == {
        "frontend": {"title": "本机标题", "apiBaseUrl": "/api"},
        "features": ["b"],
    }
    assert base["frontend"] == {"title": "基础标题", "apiBaseUrl": "/api"}


def test_load_project_config_uses_only_explicit_json_paths(tmp_path: Path) -> None:
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    project_path.write_text(
        json.dumps({"frontend": {"title": "项目", "apiBaseUrl": "/api"}}),
        encoding="utf-8",
    )
    user_path.write_text(json.dumps({"frontend": {"title": "用户"}}), encoding="utf-8")

    assert load_project_config(project_path, user_path) == {
        "frontend": {"title": "用户", "apiBaseUrl": "/api"}
    }


def test_missing_config_file_uses_safe_project_config_error(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing-project.json"
    user_path = tmp_path / "user.project.json"
    user_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError) as captured:
        load_project_config(missing_path, user_path)

    assert type(captured.value).__name__ == "ProjectConfigError"
    assert str(missing_path) in str(captured.value)
    assert "不存在" in str(captured.value)


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ('{"apiKey":"SENTINEL_CONFIG_SECRET",', "有效 JSON"),
        ('["SENTINEL_CONFIG_SECRET"]', "JSON object"),
    ],
)
def test_invalid_or_non_object_config_does_not_echo_content(
    tmp_path: Path,
    content: str,
    reason: str,
) -> None:
    project_path = tmp_path / "project.json"
    user_path = tmp_path / "user.project.json"
    project_path.write_text(content, encoding="utf-8")
    user_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError) as captured:
        project_config.load_project_config(project_path, user_path)

    assert type(captured.value).__name__ == "ProjectConfigError"
    assert reason in str(captured.value)
    assert str(project_path) in str(captured.value)
    assert "SENTINEL_CONFIG_SECRET" not in str(captured.value)
