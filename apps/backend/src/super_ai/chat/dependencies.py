"""聊天 Repository 与 service dependencies。"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.agent_audit.repositories import AgentToolCallAuditRepository
from super_ai.agent_audit.service import AgentToolAuditService
from super_ai.api_contracts import SseEvent
from super_ai.api_responses import AppError
from super_ai.auth.dependencies import bearer_scheme
from super_ai.auth.passwords import PwdlibPasswordManager
from super_ai.auth.service import AuthService, AuthServiceError
from super_ai.chat.agent_events import AgentEventMapper
from super_ai.chat.agent_tools import create_agent_tools
from super_ai.chat.memory.service import ChatMemoryService
from super_ai.chat.memory.summarizer import ChatMemorySummarizer, LangChainChatMemorySummarizer
from super_ai.chat.service import ChatService
from super_ai.chat.stream_service import AgentChatStreamService, AgentTurnRunner
from super_ai.chat_configuration.agent import ConfiguredAgentTurnRunner
from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot
from super_ai.chat_configuration.store import SqliteChatAgentConfigurationStore
from super_ai.llm.config import LlmSettings
from super_ai.llm.errors import ModelConfigurationError
from super_ai.llm.provider import QwenOpenAIProvider
from super_ai.mcp_connections.gateway import (
    LangChainMcpClientFactory,
    LangChainMcpToolGateway,
    McpToolGateway,
)
from super_ai.mcp_connections.settings import ClsMcpServerSettings
from super_ai.mcp_connections.source import ConfiguredMcpConnectionSource
from super_ai.memory.extended_sqlite.agent_audit_repositories import (
    SqliteAgentToolCallAuditRepository,
    SqliteAgentToolCallAuditStore,
)
from super_ai.memory.extended_sqlite.auth_repositories import (
    SqliteAuthSessionRepository,
    SqliteUserRepository,
)
from super_ai.memory.extended_sqlite.chat_repositories import SqliteChatRepository
from super_ai.memory.extended_sqlite.mcp_connection_repositories import (
    SqliteMcpConnectionRepository,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import PersistenceRuntime, get_session, transaction_scope
from super_ai.retrieval.factory import create_knowledge_retrieval_service
from super_ai.tenancy.context import CurrentUser
from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.config import VectorStoreSettings


def get_chat_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ChatService:
    return ChatService(SqliteChatRepository(session))


class _MissingChatMemorySummarizer:
    async def summarize(self, previous_summary: str | None, messages: object) -> str:
        raise AppError("SYSTEM_MODEL_CAPABILITY_MISSING")


def get_chat_memory_service(request: Request) -> ChatMemoryService:
    runtime = getattr(request.app.state, "persistence_runtime", None)
    if not isinstance(runtime, PersistenceRuntime):
        raise RuntimeError("持久化 runtime 尚未初始化")
    llm_settings = getattr(request.app.state, "agent_llm_settings", None)
    injected_window = getattr(request.app.state, "chat_memory_context_window_tokens", None)
    if isinstance(llm_settings, LlmSettings):
        try:
            context_window_tokens = llm_settings.capability_for_chat().context_window_tokens
        except ModelConfigurationError as error:
            raise AppError("SYSTEM_MODEL_CAPABILITY_MISSING") from error
    elif isinstance(injected_window, int) and injected_window > 0:
        context_window_tokens = injected_window
    else:
        raise AppError("SYSTEM_MODEL_CAPABILITY_MISSING")
    injected_summarizer = getattr(request.app.state, "chat_memory_summarizer", None)
    summarizer: ChatMemorySummarizer
    if injected_summarizer is not None:
        summarizer = injected_summarizer
    elif isinstance(llm_settings, LlmSettings):
        summarizer = LangChainChatMemorySummarizer(
            QwenOpenAIProvider(llm_settings).create_chat_model()
        )
    else:
        summarizer = _MissingChatMemorySummarizer()
    return ChatMemoryService(
        runtime.session_factory,
        SqliteChatAgentConfigurationStore(runtime.session_factory),
        summarizer,
        context_window_tokens=context_window_tokens,
        now=utc_now,
    )


def get_agent_audit_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentToolCallAuditRepository:
    return SqliteAgentToolCallAuditRepository(session)


def get_agent_chat_stream_service(request: Request) -> AgentChatStreamService:
    runtime = getattr(request.app.state, "persistence_runtime", None)
    if not isinstance(runtime, PersistenceRuntime):
        raise RuntimeError("持久化 runtime 尚未初始化")
    llm_settings = getattr(request.app.state, "agent_llm_settings", None)
    vector_settings = getattr(request.app.state, "agent_vector_store_settings", None)

    if not isinstance(llm_settings, LlmSettings):
        raise AppError("SYSTEM_MODEL_CAPABILITY_MISSING")
    try:
        capability_tokens = llm_settings.capability_for_chat().context_window_tokens
    except ModelConfigurationError as error:
        raise AppError("SYSTEM_MODEL_CAPABILITY_MISSING") from error
    provider = QwenOpenAIProvider(llm_settings)
    model = provider.create_chat_model()
    configuration_store = SqliteChatAgentConfigurationStore(runtime.session_factory)

    injected_gateway = getattr(request.app.state, "mcp_gateway", None)
    mcp_gateway: McpToolGateway = (
        injected_gateway
        if injected_gateway is not None
        else LangChainMcpToolGateway(LangChainMcpClientFactory())
    )
    cls_settings = getattr(request.app.state, "cls_mcp_server_settings", None)
    if not isinstance(cls_settings, ClsMcpServerSettings):
        cls_settings = ClsMcpServerSettings()

    async def runner_factory(
        current_user: CurrentUser,
        session_id: str,
        mapper: AgentEventMapper,
        emit: Callable[[SseEvent], Awaitable[None]],
        configuration: ChatAgentConfigurationSnapshot,
    ) -> AgentTurnRunner:
        if not isinstance(vector_settings, VectorStoreSettings):
            raise ModelConfigurationError("Agent chat 尚未配置 vectorStore")
        retrieval = create_knowledge_retrieval_service(
            runtime.session_factory,
            provider,
            MilvusVectorStore(vector_settings),
        )
        base_tools = create_agent_tools(current_user, retrieval, now=utc_now)
        async with transaction_scope(runtime.session_factory) as mcp_session:
            source = ConfiguredMcpConnectionSource(
                SqliteMcpConnectionRepository(mcp_session), cls_settings
            )
            targets = await source.targets_for(current_user.owner_user_id)
        mcp_tools = await mcp_gateway.discover(
            targets,
            builtin_tool_names=frozenset(
                {tool.name for tool in base_tools} | {"load_skill"}
            ),
        )
        return ConfiguredAgentTurnRunner(
            configuration_store=configuration_store,
            configuration=configuration,
            model=model,
            base_tools=(*base_tools, *mcp_tools.tools),
            mapper=mapper,
            emit=emit,
            auditor=AgentToolAuditService(
                SqliteAgentToolCallAuditStore(runtime.session_factory),
                now=utc_now,
                api_key=llm_settings.api_key.get_secret_value(),
                sensitive_tool_names=mcp_tools.mcp_tool_names,
            ),
            current_user=current_user,
            session_id=session_id,
            mcp_tool_names=mcp_tools.mcp_tool_names,
        )

    memory_service = ChatMemoryService(
        runtime.session_factory,
        configuration_store,
        LangChainChatMemorySummarizer(model),
        context_window_tokens=capability_tokens,
        now=utc_now,
    )
    return AgentChatStreamService(
        runtime.session_factory,
        runner_factory,
        memory_service,
        now=utc_now,
    )


async def get_stream_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthServiceError("AUTH_REQUIRED")
    runtime = getattr(request.app.state, "persistence_runtime", None)
    if not isinstance(runtime, PersistenceRuntime):
        raise RuntimeError("持久化 runtime 尚未初始化")
    async with transaction_scope(runtime.session_factory) as session:
        principal = await AuthService(
            SqliteUserRepository(session),
            SqliteAuthSessionRepository(session),
            PwdlibPasswordManager(),
        ).authenticate(credentials.credentials)
    return CurrentUser(principal.user.id)
