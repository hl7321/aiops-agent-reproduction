from datetime import datetime, timezone
from typing import cast

import pytest

from super_ai.api_responses import AppError
from super_ai.feedback.models import FeedbackRecord, FeedbackUpsert
from super_ai.feedback.service import FeedbackService


class FakeFeedbackRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str, str, str], FeedbackRecord] = {}

    async def list_for_target(
        self, owner_user_id: str, target_type: str, target_id: str
    ) -> list[FeedbackRecord]:
        return [
            item for key, item in self.items.items()
            if key[:3] == (owner_user_id, target_type, target_id)
        ]

    async def upsert(self, owner_user_id: str, value: FeedbackUpsert) -> FeedbackRecord:
        key = (owner_user_id, value.target_type, value.target_id, value.subject_key)
        existing = self.items.get(key)
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        item = FeedbackRecord(
            id=existing.id if existing else f"feedback-{len(self.items) + 1}",
            owner_user_id=owner_user_id,
            target_type=value.target_type,
            target_id=value.target_id,
            subject_key=value.subject_key,
            rating=value.rating,
            reason=value.reason,
            comment=value.comment,
            correction=value.correction,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.items[key] = item
        return item

    async def delete(self, owner_user_id: str, feedback_id: str) -> bool:
        for key, item in tuple(self.items.items()):
            if key[0] == owner_user_id and item.id == feedback_id:
                del self.items[key]
                return True
        return False


class FakeTargetResolver:
    def __init__(self) -> None:
        self.allowed = {
            ("owner-1", "chat_message", "message-1", ""),
            ("owner-1", "citation", "message-1", "chunk-1"),
            ("owner-1", "diagnostic_step", "step-1", ""),
            ("owner-1", "diagnostic_report", "report-1", ""),
        }

    async def validate(
        self,
        owner_user_id: str,
        target_type: str,
        target_id: str,
        subject_id: str | None,
    ) -> None:
        key = (owner_user_id, target_type, target_id, subject_id or "")
        if key not in self.allowed:
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")

    async def validate_parent(
        self, owner_user_id: str, target_type: str, target_id: str
    ) -> None:
        if not any(
            key[:3] == (owner_user_id, target_type, target_id) for key in self.allowed
        ):
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")


@pytest.mark.parametrize(
    ("target_type", "target_id", "subject"),
    [
        ("chat_message", "message-1", None),
        ("citation", "message-1", "chunk-1"),
        ("diagnostic_step", "step-1", None),
        ("diagnostic_report", "report-1", None),
    ],
)
async def test_upsert_and_restore_four_owned_targets(
    target_type: str, target_id: str, subject: str | None
) -> None:
    service = FeedbackService(FakeFeedbackRepository(), FakeTargetResolver())
    saved = await service.upsert(
        "owner-1", target_type, target_id, subject, "positive", None, "  很有帮助  ", "  "
    )
    restored = await service.list("owner-1", target_type, target_id)
    assert saved.comment == "很有帮助"
    assert saved.correction is None
    assert restored == [saved]


async def test_same_key_updates_existing_id():
    service = FeedbackService(FakeFeedbackRepository(), FakeTargetResolver())
    first = await service.upsert(
        "owner-1", "chat_message", "message-1", None, "positive", None, None, None
    )
    second = await service.upsert(
        "owner-1", "chat_message", "message-1", None, "negative", "incorrect", "错了", "应为 X"
    )
    assert second.id == first.id
    assert second.rating == "negative"


async def test_cross_owner_and_unknown_citation_are_indistinguishable():
    service = FeedbackService(FakeFeedbackRepository(), FakeTargetResolver())
    for owner, subject in (("owner-2", "chunk-1"), ("owner-1", "missing")):
        with pytest.raises(AppError) as caught:
            await service.upsert(
                owner, "citation", "message-1", subject, "negative", None, None, None
            )
        assert caught.value.code == "BUSINESS_RESOURCE_NOT_FOUND"


async def test_delete_is_owner_scoped():
    service = FeedbackService(FakeFeedbackRepository(), FakeTargetResolver())
    saved = await service.upsert(
        "owner-1", "chat_message", "message-1", None, "positive", None, None, None
    )
    with pytest.raises(AppError) as caught:
        await service.delete("owner-2", saved.id)
    assert caught.value.code == "BUSINESS_RESOURCE_NOT_FOUND"
    await service.delete("owner-1", saved.id)
    assert await service.list("owner-1", "chat_message", "message-1") == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_type": "bad"},
        {"rating": "maybe"},
        {"reason": "custom"},
        {"comment": "x" * 2001},
        {"correction": "x" * 4001},
        {"target_type": "chat_message", "subject": "not-allowed"},
    ],
)
async def test_rejects_invalid_shape_and_bounds(kwargs: dict[str, str | None]) -> None:
    values = dict(
        target_type="chat_message", target_id="message-1", subject=None,
        rating="positive", reason=None, comment=None, correction=None,
    )
    values.update(kwargs)
    service = FeedbackService(FakeFeedbackRepository(), FakeTargetResolver())
    with pytest.raises(ValueError):
        await service.upsert(
            "owner-1",
            cast(str, values["target_type"]),
            cast(str, values["target_id"]),
            values["subject"],
            cast(str, values["rating"]),
            values["reason"],
            values["comment"],
            values["correction"],
        )
