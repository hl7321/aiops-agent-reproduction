import json
from pathlib import Path

from super_ai.app import create_configured_app
from super_ai.knowledge.dependencies import get_knowledge_service


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_configured_app_uses_only_explicit_json_and_remains_network_lazy(tmp_path: Path) -> None:
    project = _write(
        tmp_path / "project.json",
        {
            "database": {"url": f"sqlite+aiosqlite:///{tmp_path / 'app.sqlite3'}"},
            "llm": {
                "provider": "qwen-openai",
                "apiKey": "test-key",
                "baseUrl": "https://qwen.example/v1",
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
                    "endpoint": "https://qwen.example/rerank",
                    "timeoutSeconds": 120,
                    "maxRetries": 2,
                },
            },
            "modelCapabilities": {"qwen3.7-max": {"contextWindowTokens": 1000}},
            "vectorStore": {
                "uri": "http://milvus.example:19530",
                "token": "token",
                "collectionName": "chunks",
            },
            "prometheusAlerts": {
                "sources": [
                    {
                        "name": "local-alertmanager",
                        "type": "alertmanager-v2",
                        "baseUrl": "http://127.0.0.1:9093",
                        "timeoutSeconds": 10,
                    }
                ]
            },
        },
    )
    user = _write(tmp_path / "user.project.json", {})

    app = create_configured_app(project, user)

    assert app.title == "智能 OnCall Agent"
    assert get_knowledge_service in app.dependency_overrides
    assert app.state.alert_settings.sources[0].name == "local-alertmanager"
