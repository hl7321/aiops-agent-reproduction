"""仅在 durable job 显式执行时组装真实 Qwen、Milvus、retrieval 与 MCP。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.agent_audit.service import AgentToolAuditService
from super_ai.aiops.cases.service import DiagnosisCasePersistor
from super_ai.aiops.planning import QwenDiagnosticModel
from super_ai.aiops.runtime import DiagnosticRuntime
from super_ai.background_jobs.handlers import BackgroundJobContext, BackgroundJobHandler
from super_ai.llm.config import LlmSettings
from super_ai.llm.provider import QwenOpenAIProvider
from super_ai.mcp_connections.gateway import (
    LangChainMcpClientFactory,
    LangChainMcpToolGateway,
    McpToolGateway,
)
from super_ai.mcp_connections.settings import ClsMcpServerSettings
from super_ai.mcp_connections.source import ConfiguredMcpConnectionSource
from super_ai.memory.extended_sqlite.agent_audit_repositories import (
    SqliteAgentToolCallAuditStore,
)
from super_ai.memory.extended_sqlite.diagnostic_repositories import SqliteDiagnosticStore
from super_ai.memory.extended_sqlite.mcp_connection_repositories import (
    SqliteMcpConnectionRepository,
)
from super_ai.memory.primitives import utc_now
from super_ai.memory.sqlite import transaction_scope
from super_ai.project_config import JsonValue
from super_ai.retrieval.factory import create_knowledge_retrieval_service
from super_ai.vector_store.adapter import MilvusVectorStore
from super_ai.vector_store.config import VectorStoreSettings


class ConfiguredDiagnosticToolResolver:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        gateway: McpToolGateway,
        fallback: ClsMcpServerSettings,
    ) -> None:
        self._sessions = sessions
        self._gateway = gateway
        self._fallback = fallback

    async def discover(
        self, owner_user_id: str, *, builtin_tool_names: frozenset[str]
    ):
        async with transaction_scope(self._sessions) as session:
            source = ConfiguredMcpConnectionSource(
                SqliteMcpConnectionRepository(session), self._fallback
            )
            targets = await source.targets_for(owner_user_id)
        discovered = await self._gateway.discover(
            targets, builtin_tool_names=builtin_tool_names
        )
        return discovered.tools


def create_configured_aiops_handler_factory(
    llm_settings: LlmSettings,
    vector_settings: VectorStoreSettings,
    cls_settings: ClsMcpServerSettings,
    gateway: McpToolGateway | None = None,
):
    """返回 lifespan factory；外部 client 延迟到真实 job 运行期创建。"""

    def factory(
        sessions: async_sessionmaker[AsyncSession],
    ) -> tuple[str, BackgroundJobHandler]:
        async def handler(context: BackgroundJobContext, payload: JsonValue) -> None:
            provider = QwenOpenAIProvider(llm_settings)
            retrieval = create_knowledge_retrieval_service(
                sessions, provider, MilvusVectorStore(vector_settings)
            )
            resolver = ConfiguredDiagnosticToolResolver(
                sessions,
                gateway or LangChainMcpToolGateway(LangChainMcpClientFactory()),
                cls_settings,
            )
            runtime = DiagnosticRuntime(
                SqliteDiagnosticStore(sessions),
                retrieval,
                resolver,
                QwenDiagnosticModel(provider.create_chat_model()),
                AgentToolAuditService(
                    SqliteAgentToolCallAuditStore(sessions),
                    now=utc_now,
                    api_key=llm_settings.api_key.get_secret_value(),
                ),
                case_persistor=DiagnosisCasePersistor(sessions),
                secret_values=(llm_settings.api_key.get_secret_value(),),
            )
            await runtime.handler()(context, payload)

        return "aiops_diagnosis", handler

    return factory
