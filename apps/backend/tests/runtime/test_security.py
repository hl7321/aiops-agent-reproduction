import json

from _pytest.logging import LogCaptureFixture

from super_ai.runtime.logging import log_lifecycle
from super_ai.runtime.security import redact_sensitive


def test_recursive_redaction_covers_nested_objects_arrays_and_key_variants() -> None:
    redacted = redact_sensitive(
        {
            "password": "p",
            "nested": [{"api_key": "k", "Authorization": "Bearer t"}],
            "safe": "visible",
        }
    )
    assert redacted == {
        "password": "[redacted]",
        "nested": [{"api_key": "[redacted]", "Authorization": "[redacted]"}],
        "safe": "visible",
    }


def test_lifecycle_log_keeps_argument_keys_and_never_argument_values(
    caplog: LogCaptureFixture,
) -> None:
    with caplog.at_level("INFO", logger="super_ai.lifecycle"):
        log_lifecycle(
            "mcp.tool",
            resource_id="call-1",
            status="failed",
            tool_name="SearchLog",
            argument_keys=("query", "authorization"),
            category="timeout",
        )
    payload = json.loads(caplog.records[-1].message)
    assert payload["argumentKeys"] == ["authorization", "query"]
    assert "argumentValues" not in payload
    assert "Bearer" not in caplog.records[-1].message
