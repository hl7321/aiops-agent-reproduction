from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.chat_configuration.service import ChatConfigurationService
from super_ai.memory.extended_sqlite.chat_configuration_repositories import (
    SqliteChatConfigurationRepository,
)
from super_ai.memory.sqlite import get_session


def get_chat_configuration_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatConfigurationService:
    return ChatConfigurationService(SqliteChatConfigurationRepository(session))
