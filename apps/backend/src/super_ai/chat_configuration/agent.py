from collections.abc import Awaitable, Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool

from super_ai.api_contracts import SseEvent
from super_ai.chat.agent_events import AgentEventMapper
from super_ai.chat.agent_runner import AgentChatRunner, AgentEventAuditor, AgentRunResult
from super_ai.chat_configuration.assembly import (
    ChatAgentConfigurationSnapshot,
    assemble_system_prompt,
)
from super_ai.chat_configuration.store import SqliteChatAgentConfigurationStore
from super_ai.chat_configuration.tools import create_load_skill_tool
from super_ai.tenancy.context import CurrentUser


class ConfiguredAgentTurnRunner:
    def __init__(
        self,
        *,
        current_user: CurrentUser,
        session_id: str,
        model: BaseChatModel,
        base_tools: Sequence[BaseTool],
        configuration_store: SqliteChatAgentConfigurationStore,
        configuration: ChatAgentConfigurationSnapshot,
        mapper: AgentEventMapper,
        emit: Callable[[SseEvent], Awaitable[None]],
        auditor: AgentEventAuditor,
        mcp_tool_names: frozenset[str] = frozenset(),
    ) -> None:
        self._current_user = current_user
        self._session_id = session_id
        self._model = model
        self._base_tools = tuple(base_tools)
        self._store = configuration_store
        self._configuration = configuration
        self._mapper = mapper
        self._emit = emit
        self._auditor = auditor
        self._mcp_tool_names = mcp_tool_names

    async def run(self, messages: Sequence[BaseMessage]) -> AgentRunResult:
        load_skill = create_load_skill_tool(
            self._current_user, self._configuration.allowed_skill_names, self._store
        )
        runner = AgentChatRunner(
            model=self._model,
            tools=(*self._base_tools, load_skill),
            system_prompt=assemble_system_prompt(self._configuration),
            mapper=self._mapper,
            emit=self._emit,
            auditor=self._auditor,
            current_user=self._current_user,
            chat_session_id=self._session_id,
            sensitive_tool_names=self._mcp_tool_names,
        )
        return await runner.run(messages)
