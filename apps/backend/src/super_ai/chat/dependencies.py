"""聊天 Repository 与 service dependencies。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.chat.service import ChatService
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.sqlite import get_session


def get_chat_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ChatService:
    return ChatService(SqliteChatRepository(session))
