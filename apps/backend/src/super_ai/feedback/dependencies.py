"""Feedback FastAPI dependencies。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.feedback.service import FeedbackService
from super_ai.feedback.targets import RepositoryFeedbackTargetResolver
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticRepository
from super_ai.memory.extended_sqlite.feedback_repositories import SqliteFeedbackRepository
from super_ai.memory.sqlite import get_session


def get_feedback_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FeedbackService:
    return FeedbackService(
        SqliteFeedbackRepository(session),
        RepositoryFeedbackTargetResolver(
            SqliteChatRepository(session), SqliteDiagnosticRepository(session)
        ),
    )
