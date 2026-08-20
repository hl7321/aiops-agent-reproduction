import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from super_ai.mcp_connections.models import McpConnectionRecord
from super_ai.mcp_connections.security import safe_mcp_error, validate_mcp_url
from super_ai.mcp_connections.settings import load_cls_mcp_server_settings
from super_ai.mcp_connections.source import ConfiguredMcpConnectionSource


@pytest.mark.parametrize(
    "url",
    ["ftp://example.test/mcp", "https:///missing-host", "https://user:pass@example.test/mcp"],
)
def test_url_validation_rejects_unsafe_urls_without_echo(url: str) -> None:
    with pytest.raises(ValueError) as captured:
        validate_mcp_url(url)
    assert "user:pass" not in str(captured.value)


def test_url_validation_preserves_legal_path_and_query() -> None:
    url = "https://example.test/mcp/path?mode=readonly"
    assert validate_mcp_url(url) == url


def test_safe_error_never_exposes_url_query_or_sentinel() -> None:
    sentinel = "MCP_SECRET_SENTINEL"
    error = RuntimeError(f"request to https://example.test/mcp?token={sentinel} failed")
    safe = safe_mcp_error(error)
    assert sentinel not in safe
    assert "token=" not in safe


def test_cls_settings_only_load_from_explicit_merged_json(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    user = tmp_path / "user.project.json"
    project.write_text(
        json.dumps(
            {
                "clsMcpServer": {
                    "baseUrl": "",
                    "transport": "streamable_http",
                    "timeoutSeconds": 30,
                    "retries": 1,
                    "secretId": "",
                    "secretKey": "",
                }
            }
        ),
        encoding="utf-8",
    )
    user.write_text(
        json.dumps({"clsMcpServer": {"baseUrl": "https://example.test/mcp"}}),
        encoding="utf-8",
    )
    settings = load_cls_mcp_server_settings(project, user)
    assert settings.base_url == "https://example.test/mcp"
    assert settings.transport == "streamable_http"
    assert settings.timeout_seconds == 30
    assert settings.retries == 1
    assert not hasattr(settings, "secret_id")


async def test_source_prefers_enabled_owner_connections_over_cls_fallback(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    enabled = McpConnectionRecord(
        "mcp-1",
        "user-1",
        "owned",
        "sse",
        "https://owned.test/sse",
        True,
        10,
        0,
        None,
        None,
        (),
        now,
        now,
    )

    class Repository:
        async def list(self, owner_user_id: str) -> tuple[McpConnectionRecord, ...]:
            assert owner_user_id == "user-1"
            return (enabled,)

    settings = load_cls_mcp_server_settings(
        _json_file(tmp_path, "p.json", {"clsMcpServer": {"baseUrl": "https://fallback.test/mcp"}}),
        _json_file(tmp_path, "u.json", {}),
    )
    targets = await ConfiguredMcpConnectionSource(Repository(), settings).targets_for("user-1")
    assert [target.id for target in targets] == ["mcp-1"]


def _json_file(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
