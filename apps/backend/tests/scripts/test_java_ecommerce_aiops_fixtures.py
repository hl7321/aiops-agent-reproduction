from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from types import ModuleType

import pytest


def _fixtures() -> ModuleType:
    try:
        return importlib.import_module("scripts.java_ecommerce_aiops_fixtures")
    except ModuleNotFoundError:
        pytest.fail("缺少 Java 电商 AIOps fixture 模块")


def test_catalog_contains_exactly_the_ten_authoritative_services() -> None:
    module = _fixtures()
    incidents = module.JAVA_ECOMMERCE_INCIDENTS

    assert len(incidents) == 10
    assert [incident.service for incident in incidents] == [
        "payment-service",
        "inventory-service",
        "order-service",
        "cart-service",
        "api-gateway",
        "promotion-service",
        "order-event-consumer",
        "product-search-service",
        "auth-service",
        "fulfillment-service",
    ]
    assert [incident.incident_id for incident in incidents] == [
        "java-ecom-001-payment-gateway-timeout",
        "java-ecom-002-inventory-lock-wait",
        "java-ecom-003-order-db-pool-exhausted",
        "java-ecom-004-cart-redis-latency",
        "java-ecom-005-checkout-circuit-open",
        "java-ecom-006-promotion-cpu-saturation",
        "java-ecom-007-order-kafka-lag",
        "java-ecom-008-product-search-timeout",
        "java-ecom-009-auth-jwk-refresh-failure",
        "java-ecom-010-fulfillment-vendor-503",
    ]


def test_catalog_has_complete_unique_stable_correlation_fields() -> None:
    module = _fixtures()
    first_read = module.JAVA_ECOMMERCE_INCIDENTS
    second_read = module.JAVA_ECOMMERCE_INCIDENTS
    unique_fields = ("incident_id", "trace_id", "service", "alertname", "sop_id")

    assert first_read is second_read
    for field in unique_fields:
        values = [getattr(incident, field) for incident in first_read]
        assert len(values) == len(set(values)) == 10
    for incident in first_read:
        assert incident.logger
        assert incident.exception
        assert incident.dependency
        assert incident.metric
        assert incident.threshold
        assert incident.symptom
        assert incident.root_cause
        assert incident.investigation
        assert incident.recovery
        assert incident.verification


def test_generated_payloads_keep_correlation_and_are_synthetic() -> None:
    module = _fixtures()
    now = datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)
    logs = module.build_java_cls_records("ap-guangzhou", now=now)
    alerts = module.build_java_alertmanager_alerts(now=now)
    sops = module.build_java_sop_documents()

    assert len(logs) == 40
    assert len(alerts) == len(sops) == 10
    for index, (incident, alert, sop) in enumerate(
        zip(module.JAVA_ECOMMERCE_INCIDENTS, alerts, sops, strict=True)
    ):
        incident_logs = logs[index * 4 : index * 4 + 4]
        assert [log["context_sequence"] for log in incident_logs] == ["1", "2", "3", "4"]
        assert [log["event_phase"] for log in incident_logs] == [
            "baseline",
            "symptom",
            "failure",
            "recovery",
        ]
        assert [log["timestamp"] for log in incident_logs] == sorted(
            log["timestamp"] for log in incident_logs
        )
        assert {log["context_flow_id"] for log in incident_logs} == {f"ctx-{incident.incident_id}"}
        for log in incident_logs:
            assert log["incident_id"] == alert["labels"]["incident_id"] == incident.incident_id
            assert log["trace_id"] == alert["labels"]["trace_id"] == incident.trace_id
            assert log["service"] == alert["labels"]["service"] == incident.service
            assert log["alertname"] == alert["labels"]["alertname"] == incident.alertname
            assert log["sop_id"] == alert["labels"]["sop_id"] == incident.sop_id
            assert log["rootCause"] == alert["annotations"]["rootCause"] == incident.root_cause
            assert log["investigation"] == " | ".join(incident.investigation)
            assert log["recovery"] == " | ".join(incident.recovery)
            assert log["verification"] == " | ".join(incident.verification)
        assert sop.metadata == {
            "knowledgeType": "aiops-sop",
            "incidentId": incident.incident_id,
            "traceId": incident.trace_id,
            "service": incident.service,
            "alertname": incident.alertname,
            "sopId": incident.sop_id,
        }

    serialized = json.dumps(
        {"logs": logs, "alerts": alerts, "sops": [item.content for item in sops]},
        ensure_ascii=False,
    ).casefold()
    for forbidden in ("secretid", "secretkey", "password", "bearer ", "customer_id"):
        assert forbidden not in serialized


def test_context_flows_are_stable_and_isolated_between_incidents() -> None:
    module = _fixtures()
    now = datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)
    first = module.build_java_cls_records("ap-guangzhou", now=now)
    second = module.build_java_cls_records("ap-guangzhou", now=now)

    assert first == second
    flow_ids = [record["context_flow_id"] for record in first]
    assert len(set(flow_ids)) == 10
    for flow_id in set(flow_ids):
        flow = [record for record in first if record["context_flow_id"] == flow_id]
        assert len(flow) == 4
        assert len({record["incident_id"] for record in flow}) == 1
        assert len({record["trace_id"] for record in flow}) == 1


def test_sop_documents_are_unique_indexable_markdown() -> None:
    module = _fixtures()
    documents = module.build_java_sop_documents()

    assert len({document.filename for document in documents}) == 10
    for incident, document in zip(module.JAVA_ECOMMERCE_INCIDENTS, documents, strict=True):
        assert document.filename == f"{incident.sop_id}.md"
        assert document.content.startswith("# Java 电商故障 SOP：")
        for value in (
            incident.incident_id,
            incident.trace_id,
            incident.service,
            incident.alertname,
            incident.exception,
            incident.dependency,
            incident.metric,
            incident.threshold,
        ):
            assert value in document.content
        for heading in ("## 故障症状", "## 根因", "## 排查步骤", "## 恢复步骤", "## 验证步骤"):
            assert heading in document.content
