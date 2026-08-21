"""反馈不可变 records 与稳定允许集合。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

FeedbackTargetType: TypeAlias = Literal[
    "chat_message", "citation", "diagnostic_step", "diagnostic_report"
]
FeedbackRating: TypeAlias = Literal["positive", "negative"]
FeedbackReason: TypeAlias = Literal[
    "incorrect", "incomplete", "irrelevant", "unclear", "unsafe", "other"
]

FEEDBACK_TARGET_TYPES = frozenset[FeedbackTargetType](
    {"chat_message", "citation", "diagnostic_step", "diagnostic_report"}
)
FEEDBACK_RATINGS = frozenset[FeedbackRating]({"positive", "negative"})
FEEDBACK_REASONS = frozenset[FeedbackReason](
    {"incorrect", "incomplete", "irrelevant", "unclear", "unsafe", "other"}
)


@dataclass(frozen=True, slots=True)
class FeedbackUpsert:
    target_type: FeedbackTargetType
    target_id: str
    subject_key: str
    rating: FeedbackRating
    reason: FeedbackReason | None
    comment: str | None
    correction: str | None


@dataclass(frozen=True, slots=True)
class FeedbackRecord:
    id: str
    owner_user_id: str
    target_type: FeedbackTargetType
    target_id: str
    subject_key: str
    rating: FeedbackRating
    reason: FeedbackReason | None
    comment: str | None
    correction: str | None
    created_at: datetime
    updated_at: datetime
