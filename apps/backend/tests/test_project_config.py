import json
from pathlib import Path

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
