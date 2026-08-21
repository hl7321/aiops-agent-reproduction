from datetime import datetime, timezone
from typing import cast

import pytest

from super_ai.aiops.models import DiagnosticReportRecord, DiagnosticStepRecord
from super_ai.aiops.repositories import DiagnosticRepository
from super_ai.api_responses import AppError
from super_ai.chat.models import ChatMessageRecord
from super_ai.chat.repositories import ChatRepository
from super_ai.feedback.targets import RepositoryFeedbackTargetResolver


class FakeChats:
    async def get_message(
        self, owner_user_id: str, message_id: str
    ) -> ChatMessageRecord | None:
        if owner_user_id != "owner-1" or message_id != "message-1":
            return None
        return ChatMessageRecord(
            "message-1", "owner-1", "session-1", "assistant", "回答", 2,
            {"references": [{"chunkId": "chunk-1"}]},
            datetime(2026, 8, 21, tzinfo=timezone.utc),
        )


class FakeDiagnostics:
    async def get_step(
        self, owner_user_id: str, step_id: str
    ) -> DiagnosticStepRecord | None:
        if (owner_user_id, step_id) != ("owner-1", "step-1"):
            return None
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        return DiagnosticStepRecord(
            "step-1", "owner-1", "task-1", 1, 0, 1, "SearchLog", {},
            "succeeded", "ok", None, now, now, now,
        )

    async def get_report(
        self, owner_user_id: str, report_id: str
    ) -> DiagnosticReportRecord | None:
        if (owner_user_id, report_id) != ("owner-1", "report-1"):
            return None
        return DiagnosticReportRecord(
            "report-1", "owner-1", "task-1", 1, "# 报告", "model", False,
            datetime(2026, 8, 21, tzinfo=timezone.utc),
        )


def resolver() -> RepositoryFeedbackTargetResolver:
    return RepositoryFeedbackTargetResolver(
        cast(ChatRepository, FakeChats()), cast(DiagnosticRepository, FakeDiagnostics())
    )


@pytest.mark.parametrize(
    ("target_type", "target_id", "subject"),
    [
        ("chat_message", "message-1", None),
        ("citation", "message-1", "chunk-1"),
        ("diagnostic_step", "step-1", None),
        ("diagnostic_report", "report-1", None),
    ],
)
async def test_resolver_accepts_only_owned_real_target(
    target_type: str, target_id: str, subject: str | None
) -> None:
    await resolver().validate("owner-1", target_type, target_id, subject)
    with pytest.raises(AppError) as caught:
        await resolver().validate("owner-2", target_type, target_id, subject)
    assert caught.value.code == "BUSINESS_RESOURCE_NOT_FOUND"


async def test_citation_must_exist_in_assistant_metadata() -> None:
    with pytest.raises(AppError) as caught:
        await resolver().validate("owner-1", "citation", "message-1", "invented")
    assert caught.value.code == "BUSINESS_RESOURCE_NOT_FOUND"
