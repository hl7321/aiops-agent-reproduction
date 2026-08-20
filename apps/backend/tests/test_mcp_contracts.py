from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from super_ai.api_contracts import (
    CreateMcpConnectionRequest,
    McpConnection,
    McpConnectionCheckResult,
    McpDiscoveredTool,
)


def test_mcp_contract_serializes_shared_camel_case_shape() -> None:
    now = datetime(2026, 8, 20, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    tool = McpDiscoveredTool(name="query_logs", description=None)
    connection = McpConnection(
        id="mcp-1",
        name="CLS",
        transport="streamable_http",
        url="https://example.test/mcp?mode=read",
        enabled=True,
        timeoutSeconds=30,
        retries=1,
        lastCheck=now,
        lastError=None,
        discoveredTools=[tool],
        createdAt=now,
        updatedAt=now,
    )
    payload = McpConnectionCheckResult(
        status="connected", connection=connection, tools=[tool], error=None
    ).model_dump(mode="json", by_alias=True)

    assert payload["connection"]["timeoutSeconds"] == 30
    assert payload["connection"]["url"].endswith("?mode=read")
    assert payload["tools"] == [{"name": "query_logs", "description": None}]


@pytest.mark.parametrize(
    ("field", "value"),
    [("timeoutSeconds", 0), ("timeoutSeconds", 301), ("retries", -1), ("retries", 6)],
)
def test_mcp_request_rejects_ranges(field: str, value: int) -> None:
    body = {
        "name": "CLS",
        "transport": "sse",
        "url": "https://example.test/sse",
        "enabled": True,
        "timeoutSeconds": 30,
        "retries": 1,
    }
    body[field] = value
    with pytest.raises(ValidationError):
        CreateMcpConnectionRequest.model_validate(body)


def test_mcp_request_rejects_blank_normalized_name() -> None:
    with pytest.raises(ValidationError):
        CreateMcpConnectionRequest.model_validate(
            {
                "name": "   ",
                "transport": "sse",
                "url": "https://example.test/sse",
            }
        )
