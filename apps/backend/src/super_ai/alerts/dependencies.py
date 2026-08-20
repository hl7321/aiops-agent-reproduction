"""活跃告警 request-scoped provider/client 依赖。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack

import httpx
from fastapi import Request

from super_ai.alerts.providers import AlertmanagerV2AlertProvider, PrometheusV1AlertProvider
from super_ai.alerts.service import AlertAggregator, AlertProvider
from super_ai.alerts.settings import AlertSourceSettings, PrometheusAlertsSettings


def create_alert_http_client(
    source: AlertSourceSettings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    auth = (
        httpx.BasicAuth(source.basic_auth.username, source.basic_auth.password)
        if source.basic_auth is not None
        else None
    )
    return httpx.AsyncClient(
        auth=auth,
        timeout=source.timeout_seconds,
        transport=transport,
    )


async def get_alert_aggregator(request: Request) -> AsyncIterator[AlertAggregator]:
    settings = getattr(request.app.state, "alert_settings", PrometheusAlertsSettings())
    if not isinstance(settings, PrometheusAlertsSettings):
        raise RuntimeError("alert settings 尚未初始化")
    async with AsyncExitStack() as stack:
        providers: list[AlertProvider] = []
        for source in settings.sources:
            client = await stack.enter_async_context(create_alert_http_client(source))
            if source.source_type == "prometheus-v1":
                providers.append(PrometheusV1AlertProvider(source, client))
            else:
                providers.append(AlertmanagerV2AlertProvider(source, client))
        yield AlertAggregator(providers)
