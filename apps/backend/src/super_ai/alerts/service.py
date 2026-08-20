"""多来源活跃告警并发聚合。"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol

from super_ai.alerts.models import ActiveAlertRecord
from super_ai.api_responses import AppError


class AlertProvider(Protocol):
    async def fetch_active_alerts(self) -> tuple[ActiveAlertRecord, ...]: ...


class AlertAggregator:
    def __init__(self, providers: Sequence[AlertProvider]) -> None:
        self._providers = tuple(providers)

    async def list_active(self) -> tuple[ActiveAlertRecord, ...]:
        if not self._providers:
            raise AppError("SYSTEM_ALERT_SOURCES_UNAVAILABLE")
        outcomes = await asyncio.gather(
            *(provider.fetch_active_alerts() for provider in self._providers),
            return_exceptions=True,
        )
        successful_sources = 0
        alerts: list[ActiveAlertRecord] = []
        for outcome in outcomes:
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome
            if isinstance(outcome, BaseException):
                continue
            successful_sources += 1
            alerts.extend(outcome)
        if successful_sources == 0:
            raise AppError("SYSTEM_ALERT_SOURCES_UNAVAILABLE")
        return tuple(
            sorted(
                alerts,
                key=lambda item: (item.source.name, item.starts_at, item.alert_name),
            )
        )
