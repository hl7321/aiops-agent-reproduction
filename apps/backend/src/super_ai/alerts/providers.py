"""Prometheus v1 与 Alertmanager v2 活跃告警 provider。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from super_ai.alerts.models import ActiveAlertRecord, ActiveAlertStatus, AlertSourceRecord
from super_ai.alerts.settings import AlertSourceSettings

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class AlertProviderError(RuntimeError):
    """不包含 URL、凭据或上游响应正文的 provider 安全错误。"""


class _ProviderModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class _PrometheusAlert(_ProviderModel):
    active_at: datetime = Field(alias="activeAt")
    annotations: dict[str, str] = Field(default_factory=dict)
    labels: dict[str, str]
    state: Literal["pending", "firing"]


class _PrometheusData(_ProviderModel):
    alerts: list[_PrometheusAlert]


class _PrometheusResponse(_ProviderModel):
    status: Literal["success"]
    data: _PrometheusData


class _AlertmanagerStatus(_ProviderModel):
    state: Literal["active", "suppressed", "unprocessed"]


class _AlertmanagerAlert(_ProviderModel):
    annotations: dict[str, str] = Field(default_factory=dict)
    labels: dict[str, str]
    starts_at: datetime = Field(alias="startsAt")
    status: _AlertmanagerStatus


_ALERTMANAGER_RESPONSE = TypeAdapter(list[_AlertmanagerAlert])


class PrometheusV1AlertProvider:
    def __init__(self, source: AlertSourceSettings, client: httpx.AsyncClient) -> None:
        self.source = source
        self._client = client

    async def fetch_active_alerts(self) -> tuple[ActiveAlertRecord, ...]:
        try:
            response = await self._client.get(f"{self.source.base_url}/api/v1/alerts")
            response.raise_for_status()
            parsed = _PrometheusResponse.model_validate(response.json())
            return tuple(self._to_record(alert) for alert in parsed.data.alerts)
        except (httpx.HTTPError, KeyError, ValueError, ValidationError):
            raise AlertProviderError(f"{self.source.name} 告警请求失败") from None

    def _to_record(self, alert: _PrometheusAlert) -> ActiveAlertRecord:
        return ActiveAlertRecord(
            alert_name=alert.labels["alertname"],
            service=alert.labels.get("service"),
            severity=alert.labels.get("severity"),
            status=alert.state,
            starts_at=_utc_iso(alert.active_at),
            labels=dict(alert.labels),
            annotations=dict(alert.annotations),
            source=AlertSourceRecord(self.source.name, self.source.source_type),
            raw_context=_JSON_OBJECT.validate_python(
                alert.model_dump(mode="json", by_alias=True, exclude_none=False)
            ),
        )


class AlertmanagerV2AlertProvider:
    _STATUS_MAP: dict[str, ActiveAlertStatus] = {
        "active": "firing",
        "suppressed": "suppressed",
        "unprocessed": "unprocessed",
    }

    def __init__(self, source: AlertSourceSettings, client: httpx.AsyncClient) -> None:
        self.source = source
        self._client = client

    async def fetch_active_alerts(self) -> tuple[ActiveAlertRecord, ...]:
        try:
            response = await self._client.get(
                f"{self.source.base_url}/api/v2/alerts", params={"active": "true"}
            )
            response.raise_for_status()
            parsed = _ALERTMANAGER_RESPONSE.validate_python(response.json())
            return tuple(self._to_record(alert) for alert in parsed)
        except (httpx.HTTPError, KeyError, ValueError, ValidationError):
            raise AlertProviderError(f"{self.source.name} 告警请求失败") from None

    def _to_record(self, alert: _AlertmanagerAlert) -> ActiveAlertRecord:
        return ActiveAlertRecord(
            alert_name=alert.labels["alertname"],
            service=alert.labels.get("service"),
            severity=alert.labels.get("severity"),
            status=self._STATUS_MAP[alert.status.state],
            starts_at=_utc_iso(alert.starts_at),
            labels=dict(alert.labels),
            annotations=dict(alert.annotations),
            source=AlertSourceRecord(self.source.name, self.source.source_type),
            raw_context=_JSON_OBJECT.validate_python(
                alert.model_dump(mode="json", by_alias=True, exclude_none=False)
            ),
        )


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("告警时间必须包含时区")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
