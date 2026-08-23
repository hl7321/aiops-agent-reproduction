"""反馈持久化与目标验证 Protocol。"""

from typing import Protocol

from super_ai.feedback.models import FeedbackRecord, FeedbackUpsert


class FeedbackRepository(Protocol):
    async def list_for_target(
        self, owner_user_id: str, target_type: str, target_id: str
    ) -> list[FeedbackRecord]: ...
    async def upsert(self, owner_user_id: str, value: FeedbackUpsert) -> FeedbackRecord: ...
    async def get_subject(
        self,
        owner_user_id: str,
        target_type: str,
        target_id: str,
        subject_key: str,
    ) -> FeedbackRecord | None: ...
    async def delete(self, owner_user_id: str, feedback_id: str) -> bool: ...


class FeedbackTargetResolver(Protocol):
    async def validate(
        self,
        owner_user_id: str,
        target_type: str,
        target_id: str,
        subject_id: str | None,
    ) -> None: ...
    async def validate_parent(
        self, owner_user_id: str, target_type: str, target_id: str
    ) -> None: ...
