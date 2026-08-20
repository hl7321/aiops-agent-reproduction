from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from super_ai.alerts.models import ActiveAlertRecord, AlertSourceRecord
from super_ai.alerts.providers import AlertProviderError
from super_ai.alerts.service import AlertAggregator
from super_ai.api_responses import AppError


def _alert(source: str, starts_at: str, name: str) -> ActiveAlertRecord:
    return ActiveAlertRecord(
        alert_name=name,
        service=None,
        severity=None,
        status="firing",
        starts_at=starts_at,
        labels={"alertname": name},
        annotations={},
        source=AlertSourceRecord(source, "prometheus-v1"),
        raw_context={"state": "firing"},
    )


@dataclass
class _StaticProvider:
    source_name: str
    result: tuple[ActiveAlertRecord, ...] = ()
    failure: bool = False

    async def fetch_active_alerts(self) -> tuple[ActiveAlertRecord, ...]:
        if self.failure:
            raise AlertProviderError(f"{self.source_name} failed")
        return self.result


async def test_aggregator_starts_sources_concurrently() -> None:
    started: set[str] = set()
    both_started = asyncio.Event()

    @dataclass
    class BlockingProvider:
        source_name: str

        async def fetch_active_alerts(self) -> tuple[ActiveAlertRecord, ...]:
            started.add(self.source_name)
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.5)
            return ()

    result = await AlertAggregator(
        [BlockingProvider("one"), BlockingProvider("two")]
    ).list_active()

    assert result == ()
    assert started == {"one", "two"}


async def test_aggregator_keeps_successful_source_and_sorts_deterministically() -> None:
    aggregator = AlertAggregator(
        [
            _StaticProvider("failed", failure=True),
            _StaticProvider(
                "successful",
                result=(
                    _alert("z-source", "2026-08-20T02:00:00Z", "B"),
                    _alert("a-source", "2026-08-20T03:00:00Z", "C"),
                    _alert("a-source", "2026-08-20T01:00:00Z", "A"),
                ),
            ),
        ]
    )

    result = await aggregator.list_active()

    assert [(item.source.name, item.starts_at, item.alert_name) for item in result] == [
        ("a-source", "2026-08-20T01:00:00Z", "A"),
        ("a-source", "2026-08-20T03:00:00Z", "C"),
        ("z-source", "2026-08-20T02:00:00Z", "B"),
    ]


async def test_aggregator_treats_successful_empty_source_as_success() -> None:
    result = await AlertAggregator(
        [_StaticProvider("empty"), _StaticProvider("failed", failure=True)]
    ).list_active()

    assert result == ()


@pytest.mark.parametrize(
    "providers",
    [[], [_StaticProvider("one", failure=True), _StaticProvider("two", failure=True)]],
)
async def test_aggregator_raises_stable_503_when_no_source_succeeds(
    providers: list[_StaticProvider],
) -> None:
    with pytest.raises(AppError) as error:
        await AlertAggregator(providers).list_active()

    assert error.value.code == "SYSTEM_ALERT_SOURCES_UNAVAILABLE"
    assert error.value.safe_message == "活跃告警来源暂时不可用"
    assert error.value.details is None
