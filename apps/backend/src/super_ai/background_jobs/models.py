"""后台任务不可变领域 records。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, TypeAlias

from super_ai.project_config import JsonValue

BackgroundJobStatus: TypeAlias = Literal["queued", "running", "succeeded", "failed", "cancelled"]
BackgroundJobEventType: TypeAlias = Literal[
    "queued", "running", "succeeded", "failed", "cancelled", "progress"
]


def _empty_payload() -> JsonValue:
    return {}


@dataclass(frozen=True, slots=True)
class NewBackgroundJob:
    kind: str
    payload: JsonValue = field(default_factory=_empty_payload)
    resource_type: str | None = None
    resource_id: str | None = None
    max_attempts: int = 3
    timeout_seconds: int = 300
    available_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("kind 不得为空")
        if self.max_attempts < 1:
            raise ValueError("max_attempts 必须大于零")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds 必须大于零")


@dataclass(frozen=True, slots=True)
class BackgroundJobRecord:
    id: str
    owner_user_id: str
    kind: str
    resource_type: str | None
    resource_id: str | None
    status: BackgroundJobStatus
    payload: JsonValue
    attempt: int
    max_attempts: int
    timeout_seconds: int
    available_at: datetime
    lease_owner: str | None
    lease_expires_at: datetime | None
    cancel_requested_at: datetime | None
    retry_of_job_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class BackgroundJobEventRecord:
    sequence: int
    job_id: str
    owner_user_id: str
    type: BackgroundJobEventType
    data: JsonValue
    created_at: datetime
