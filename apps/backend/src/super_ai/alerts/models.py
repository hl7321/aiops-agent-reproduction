"""告警聚合领域记录。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from super_ai.alerts.settings import AlertSourceType

ActiveAlertStatus = Literal["pending", "firing", "suppressed", "unprocessed"]


@dataclass(frozen=True, slots=True)
class AlertSourceRecord:
    name: str
    source_type: AlertSourceType


@dataclass(frozen=True, slots=True)
class ActiveAlertRecord:
    alert_name: str
    service: str | None
    severity: str | None
    status: ActiveAlertStatus
    starts_at: str
    labels: dict[str, str]
    annotations: dict[str, str]
    source: AlertSourceRecord
    raw_context: dict[str, JsonValue]
