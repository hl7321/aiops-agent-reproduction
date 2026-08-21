"""结构化反馈用例服务。"""

from super_ai.api_responses import AppError
from super_ai.feedback.models import (
    FEEDBACK_RATINGS,
    FEEDBACK_REASONS,
    FEEDBACK_TARGET_TYPES,
    FeedbackRecord,
    FeedbackTargetType,
    FeedbackUpsert,
)
from super_ai.feedback.repositories import FeedbackRepository, FeedbackTargetResolver


def _trim(value: str | None, *, maximum: int, label: str) -> str | None:
    normalized = value.strip() if value is not None else ""
    if len(normalized) > maximum:
        raise ValueError(f"{label} 超过长度上限")
    return normalized or None


class FeedbackService:
    def __init__(
        self, repository: FeedbackRepository, target_resolver: FeedbackTargetResolver
    ) -> None:
        self._repository = repository
        self._targets = target_resolver

    async def list(
        self, owner_user_id: str, target_type: str, target_id: str
    ) -> list[FeedbackRecord]:
        checked_type = self._target_type(target_type)
        checked_id = self._required(target_id, "targetId")
        await self._targets.validate_parent(owner_user_id, checked_type, checked_id)
        return await self._repository.list_for_target(owner_user_id, checked_type, checked_id)

    async def upsert(
        self,
        owner_user_id: str,
        target_type: str,
        target_id: str,
        subject: str | None,
        rating: str,
        reason: str | None,
        comment: str | None,
        correction: str | None,
    ) -> FeedbackRecord:
        checked_type = self._target_type(target_type)
        checked_id = self._required(target_id, "targetId")
        checked_subject = subject.strip() if subject is not None else None
        if checked_subject == "":
            checked_subject = None
        if checked_type == "citation":
            if checked_subject is None:
                raise ValueError("citation 必须提供 subjectId")
        elif checked_subject is not None:
            raise ValueError(f"{checked_type} 不接受 subjectId")
        if rating not in FEEDBACK_RATINGS:
            raise ValueError("rating 不受支持")
        normalized_reason = reason.strip() if reason is not None else ""
        if normalized_reason and normalized_reason not in FEEDBACK_REASONS:
            raise ValueError("reason 不受支持")
        await self._targets.validate(
            owner_user_id, checked_type, checked_id, checked_subject
        )
        return await self._repository.upsert(
            owner_user_id,
            FeedbackUpsert(
                checked_type,
                checked_id,
                checked_subject or "",
                rating,
                normalized_reason or None,
                _trim(comment, maximum=2000, label="comment"),
                _trim(correction, maximum=4000, label="correction"),
            ),
        )

    async def delete(self, owner_user_id: str, feedback_id: str) -> None:
        if not await self._repository.delete(
            owner_user_id, self._required(feedback_id, "feedbackId")
        ):
            raise AppError("BUSINESS_RESOURCE_NOT_FOUND")

    @staticmethod
    def _target_type(value: str) -> FeedbackTargetType:
        if value not in FEEDBACK_TARGET_TYPES:
            raise ValueError("targetType 不受支持")
        return value

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label} 不得为空")
        return normalized
