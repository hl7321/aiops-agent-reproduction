"""单进程轻量 HTTP 指标。"""

from __future__ import annotations

from threading import Lock

from super_ai.runtime.models import ProcessMetrics


class ProcessMetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests = 0
        self._failures = 0
        self._duration_ms = 0.0

    def observe(self, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._requests += 1
            self._failures += int(status_code >= 400)
            self._duration_ms += max(0.0, duration_ms)

    def snapshot(self) -> ProcessMetrics:
        with self._lock:
            average = self._duration_ms / self._requests if self._requests else 0.0
            return ProcessMetrics(
                requestCount=self._requests,
                failureCount=self._failures,
                totalDurationMs=round(self._duration_ms, 3),
                averageDurationMs=round(average, 3),
            )
