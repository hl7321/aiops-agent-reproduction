from super_ai.api_contracts import ERROR_DEFINITIONS, ActiveAlert, ActiveAlertsData, AlertSource


def test_python_active_alert_contract_matches_public_shape() -> None:
    alert = ActiveAlert(
        alertName="HighErrorRate",
        service=None,
        severity="critical",
        status="firing",
        startsAt="2026-08-20T00:00:00Z",
        labels={"alertname": "HighErrorRate"},
        annotations={"summary": "错误率升高"},
        source=AlertSource(name="prometheus-main", type="prometheus-v1"),
        rawContext={"state": "firing", "value": "1"},
    )

    dumped = ActiveAlertsData(items=[alert]).model_dump(mode="json", by_alias=True)
    assert dumped == {
        "items": [
            {
                "alertName": "HighErrorRate",
                "service": None,
                "severity": "critical",
                "status": "firing",
                "startsAt": "2026-08-20T00:00:00Z",
                "labels": {"alertname": "HighErrorRate"},
                "annotations": {"summary": "错误率升高"},
                "source": {"name": "prometheus-main", "type": "prometheus-v1"},
                "rawContext": {"state": "firing", "value": "1"},
            }
        ]
    }
    assert ERROR_DEFINITIONS["SYSTEM_ALERT_SOURCES_UNAVAILABLE"].to_contract() == {
        "code": "SYSTEM_ALERT_SOURCES_UNAVAILABLE",
        "category": "system",
        "httpStatus": 503,
        "defaultMessage": "活跃告警来源暂时不可用",
    }
