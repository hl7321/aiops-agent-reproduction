"""结构化反馈 owner-scoped SQLite adapter。"""

from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.feedback.models import (
    FeedbackRating,
    FeedbackReason,
    FeedbackRecord,
    FeedbackTargetType,
    FeedbackUpsert,
)
from super_ai.memory.extended_sqlite.feedback_models import UserFeedbackModel
from super_ai.memory.primitives import new_id, utc_now


class SqliteFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_target(
        self, owner_user_id: str, target_type: str, target_id: str
    ) -> list[FeedbackRecord]:
        models = (
            await self._session.scalars(
                select(UserFeedbackModel)
                .where(
                    UserFeedbackModel.owner_user_id == owner_user_id,
                    UserFeedbackModel.target_type == target_type,
                    UserFeedbackModel.target_id == target_id,
                )
                .order_by(UserFeedbackModel.subject_key, UserFeedbackModel.id)
            )
        ).all()
        return [_record(item) for item in models]

    async def upsert(self, owner_user_id: str, value: FeedbackUpsert) -> FeedbackRecord:
        now = utc_now()
        statement = insert(UserFeedbackModel).values(
            id=new_id(),
            owner_user_id=owner_user_id,
            target_type=value.target_type,
            target_id=value.target_id,
            subject_key=value.subject_key,
            rating=value.rating,
            reason=value.reason,
            comment=value.comment,
            correction=value.correction,
            created_at=now,
            updated_at=now,
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    "owner_user_id", "target_type", "target_id", "subject_key"
                ],
                set_={
                    "rating": value.rating,
                    "reason": value.reason,
                    "comment": value.comment,
                    "correction": value.correction,
                    "updated_at": now,
                },
            )
        )
        model = await self._session.scalar(
            select(UserFeedbackModel).where(
                UserFeedbackModel.owner_user_id == owner_user_id,
                UserFeedbackModel.target_type == value.target_type,
                UserFeedbackModel.target_id == value.target_id,
                UserFeedbackModel.subject_key == value.subject_key,
            )
        )
        if model is None:
            raise RuntimeError("反馈 upsert 后无法读取记录")
        return _record(model)

    async def get_subject(
        self,
        owner_user_id: str,
        target_type: str,
        target_id: str,
        subject_key: str,
    ) -> FeedbackRecord | None:
        model = await self._session.scalar(
            select(UserFeedbackModel).where(
                UserFeedbackModel.owner_user_id == owner_user_id,
                UserFeedbackModel.target_type == target_type,
                UserFeedbackModel.target_id == target_id,
                UserFeedbackModel.subject_key == subject_key,
            )
        )
        return _record(model) if model is not None else None

    async def delete(self, owner_user_id: str, feedback_id: str) -> bool:
        deleted = await self._session.scalar(
            delete(UserFeedbackModel)
            .where(
                UserFeedbackModel.owner_user_id == owner_user_id,
                UserFeedbackModel.id == feedback_id,
            )
            .returning(UserFeedbackModel.id)
        )
        return deleted is not None


def _record(model: UserFeedbackModel) -> FeedbackRecord:
    return FeedbackRecord(
        model.id,
        model.owner_user_id,
        cast(FeedbackTargetType, model.target_type),
        model.target_id,
        model.subject_key,
        cast(FeedbackRating, model.rating),
        cast(FeedbackReason | None, model.reason),
        model.comment,
        model.correction,
        model.created_at,
        model.updated_at,
    )
