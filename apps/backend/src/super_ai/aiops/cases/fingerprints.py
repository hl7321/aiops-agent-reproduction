"""canonical diagnostic case 的版本化稳定摘要与相似度。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence

from super_ai.aiops.cases.models import CaseMaterial, DiagnosisCaseRecord
from super_ai.project_config import JsonValue

FINGERPRINT_VERSION = "v1"


def case_fingerprints(
    material: CaseMaterial, alerts: Sequence[Mapping[str, JsonValue]]
) -> tuple[str, str]:
    first: Mapping[str, JsonValue] = alerts[0] if alerts else {}
    dependency = _normalize(first.get("dependency"))
    incident = _digest(
        {
            "version": FINGERPRINT_VERSION,
            "service": _normalize(material.service),
            "alertName": _normalize(material.alert_name),
            "dependency": dependency,
            "rootCause": _normalize(material.root_cause),
            "remediation": _normalize(material.remediation),
        }
    )
    knowledge = _digest(
        {
            "version": FINGERPRINT_VERSION,
            "alertName": _normalize(material.alert_name),
            "service": _normalize(material.service),
            "summary": _normalize(material.summary),
            "rootCause": _normalize(material.root_cause),
            "remediation": _normalize(material.remediation),
        }
    )
    return incident, knowledge


def case_similarity(material: CaseMaterial, existing: DiagnosisCaseRecord) -> float:
    left = _tokens(
        " ".join(
            (material.alert_name, material.service, material.root_cause, material.remediation)
        )
    )
    right = _tokens(
        " ".join(
            (existing.alert_name, existing.service, existing.root_cause, existing.remediation)
        )
    )
    if not left or not right:
        return 0.0
    return round(len(left & right) / len(left | right), 6)


def _digest(value: Mapping[str, str]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize(value: JsonValue | None) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().strip().split())


def _tokens(value: str) -> set[str]:
    normalized = " ".join(value.casefold().split())
    ascii_tokens = set(re.findall(r"[a-z0-9_.-]+", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    return ascii_tokens | {chinese[index : index + 2] for index in range(len(chinese) - 1)}
