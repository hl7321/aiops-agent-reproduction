"""按 kind 注册的后台任务 handler 边界。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from super_ai.project_config import JsonValue

CancellationCheck = Callable[[], Awaitable[bool]]
BackgroundJobTerminationReason: TypeAlias = Literal["cancelled", "timeout", "shutdown"]
TerminationReasonReader = Callable[[], BackgroundJobTerminationReason | None]


def _no_termination_reason() -> BackgroundJobTerminationReason | None:
    return None


BackgroundJobHandler = Callable[["BackgroundJobContext", JsonValue], Coroutine[Any, Any, None]]


class BackgroundJobCancelledError(Exception):
    """handler 在协作检查点观察到取消请求。"""


@dataclass(frozen=True, slots=True)
class BackgroundJobContext:
    job_id: str
    owner_user_id: str
    _cancellation_check: CancellationCheck
    _termination_reason: TerminationReasonReader = field(default=_no_termination_reason)

    async def raise_if_cancelled(self) -> None:
        if await self._cancellation_check():
            raise BackgroundJobCancelledError

    async def cancellation_requested(self) -> bool:
        """区分用户取消与 worker shutdown；后者不得误写领域 cancelled。"""
        return await self._cancellation_check()

    @property
    def termination_reason(self) -> BackgroundJobTerminationReason | None:
        return self._termination_reason()


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, BackgroundJobHandler] = {}

    def register(self, kind: str, handler: BackgroundJobHandler) -> None:
        normalized = kind.strip()
        if not normalized:
            raise ValueError("handler kind 不得为空")
        if normalized in self._handlers:
            raise ValueError(f"handler 已注册: {normalized}")
        self._handlers[normalized] = handler

    def get(self, kind: str) -> BackgroundJobHandler | None:
        return self._handlers.get(kind)
