"""LangChain create_agent 的可注入单轮运行边界。"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from langchain.agents import create_agent  # pyright: ignore[reportUnknownVariableType]
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool

from super_ai.api_contracts import (
    LANGCHAIN_ERROR_FIELD,
    LANGCHAIN_TEXT_BLOCK_TYPE,
    ApiErrorModel,
    ChatReference,
    SseEvent,
)
from super_ai.chat.agent_events import AgentEventMapper
from super_ai.project_config import JsonValue
from super_ai.tenancy.context import CurrentUser


class AgentGraph(Protocol):
    def astream_events(
        self, value: dict[str, object], *, version: str
    ) -> AsyncIterator[dict[str, object]]: ...


AgentFactory = Callable[[BaseChatModel, Sequence[BaseTool], str], AgentGraph]
EventSink = Callable[[SseEvent], Awaitable[None]]


class AgentEventAuditor(Protocol):
    async def start_tool(
        self,
        current_user: CurrentUser,
        *,
        chat_session_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> None: ...

    async def complete_tool(self, current_user: CurrentUser, tool_call_id: str) -> None: ...

    async def fail_tool(
        self, current_user: CurrentUser, tool_call_id: str, *, error: Exception
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    final_text: str
    references: tuple[ChatReference, ...]
    tool_call_ids: tuple[str, ...]


class AgentChatRunner:
    def __init__(
        self,
        *,
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        system_prompt: str = (
            "你是智能 OnCall 助手。根据用户问题自主判断是否需要调用工具；"
            "不得编造工具结果或引用。"
        ),
        mapper: AgentEventMapper,
        agent_factory: AgentFactory | None = None,
        emit: EventSink,
        auditor: AgentEventAuditor | None = None,
        current_user: CurrentUser | None = None,
        chat_session_id: str | None = None,
        sensitive_tool_names: frozenset[str] = frozenset(),
    ) -> None:
        self._model = model
        self._tools = tuple(tools)
        self._system_prompt = system_prompt
        self._mapper = mapper
        self._agent_factory = agent_factory or _create_agent
        self._emit = emit
        self._auditor = auditor
        self._current_user = current_user
        self._chat_session_id = chat_session_id
        self._sensitive_tool_names = sensitive_tool_names
        if auditor is not None and (current_user is None or chat_session_id is None):
            raise ValueError("启用工具审计时必须提供 current_user 与 chat_session_id")

    async def run(self, messages: Sequence[BaseMessage]) -> AgentRunResult:
        agent = self._agent_factory(self._model, self._tools, self._system_prompt)
        model_buffers: dict[str, list[str]] = {}
        model_order: list[str] = []
        async for raw_event in agent.astream_events({"messages": list(messages)}, version="v2"):
            await self._handle_event(raw_event, model_buffers, model_order)
        final_text = "" if not model_order else "".join(model_buffers[model_order[-1]])
        context = self._mapper.context
        return AgentRunResult(final_text, context.references, context.tool_call_ids)

    async def _handle_event(
        self,
        raw_event: dict[str, object],
        model_buffers: dict[str, list[str]],
        model_order: list[str],
    ) -> None:
        event_name = raw_event.get("event")
        run_id = str(raw_event.get("run_id") or "")
        data = raw_event.get("data")
        if not isinstance(data, dict):
            return
        data_map = cast(dict[str, object], data)
        if event_name == "on_chat_model_stream":
            chunk = data_map.get("chunk")
            if not isinstance(chunk, AIMessageChunk):
                return
            if run_id not in model_buffers:
                model_buffers[run_id] = []
                model_order.append(run_id)
            text = _chunk_text(chunk.content)
            if text:
                model_buffers[run_id].append(text)
            reasoning = chunk.additional_kwargs.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                await self._emit(self._mapper.reasoning(reasoning))
            return
        if event_name == "on_tool_start":
            tool_name = str(raw_event.get("name") or "tool")
            arguments = _arguments(data_map.get("input"))
            safe_arguments = (
                _provided_arguments(arguments)
                if tool_name in self._sensitive_tool_names
                else arguments
            )
            if self._auditor is not None:
                assert self._current_user is not None and self._chat_session_id is not None
                await self._auditor.start_tool(
                    self._current_user,
                    chat_session_id=self._chat_session_id,
                    tool_call_id=run_id,
                    tool_name=tool_name,
                    arguments=safe_arguments,
                )
            await self._emit(
                self._mapper.tool_call(
                    run_id,
                    tool_name,
                    "started",
                    input=cast(JsonValue, safe_arguments),
                )
            )
            return
        if event_name == "on_tool_end":
            tool_name = str(raw_event.get("name") or "tool")
            output = _normalize_tool_output(data_map.get("output"))
            if self._auditor is not None:
                assert self._current_user is not None
                await self._auditor.complete_tool(self._current_user, run_id)
            safe_output: JsonValue = (
                {"status": "completed"}
                if tool_name in self._sensitive_tool_names
                else output
            )
            await self._emit(
                self._mapper.tool_call(run_id, tool_name, "completed", output=safe_output)
            )
            if tool_name == "knowledge_retrieval":
                for reference in _references(output):
                    await self._emit(self._mapper.reference(reference))
            return
        if event_name == "on_tool_error":
            tool_name = str(raw_event.get("name") or "tool")
            if self._auditor is not None:
                assert self._current_user is not None
                raw_error = data_map.get(LANGCHAIN_ERROR_FIELD)
                if tool_name in self._sensitive_tool_names:
                    error = RuntimeError("MCP 工具调用失败")
                else:
                    error = (
                        raw_error
                        if isinstance(raw_error, Exception)
                        else RuntimeError("工具调用失败")
                    )
                await self._auditor.fail_tool(self._current_user, run_id, error=error)
            await self._emit(
                self._mapper.tool_call(
                    run_id,
                    tool_name,
                    "failed",
                    error=_safe_error(),
                )
            )


def _create_agent(
    model: BaseChatModel, tools: Sequence[BaseTool], system_prompt: str
) -> AgentGraph:
    return cast(
        AgentGraph,
        create_agent(
            model,
            list(tools),
            system_prompt=system_prompt,
        ),
    )


def _chunk_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in cast(list[object], content):
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            block_map = cast(dict[str, object], block)
            if block_map.get("type") != LANGCHAIN_TEXT_BLOCK_TYPE:
                continue
            text = block_map.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _references(output: object) -> tuple[ChatReference, ...]:
    if not isinstance(output, dict):
        return ()
    output_map = cast(dict[str, object], output)
    results = output_map.get("results")
    if not isinstance(results, list):
        return ()
    references: list[ChatReference] = []
    for result in cast(list[object], results):
        if not isinstance(result, dict):
            continue
        try:
            references.append(ChatReference.model_validate(cast(dict[str, object], result)))
        except ValueError:
            continue
    return tuple(references)


def _normalize_tool_output(output: object) -> JsonValue:
    if isinstance(output, ToolMessage):
        output = output.artifact if output.artifact is not None else output.content
    if isinstance(output, str):
        try:
            return cast(JsonValue, json.loads(output))
        except json.JSONDecodeError:
            return output
    return cast(JsonValue, output)


def _safe_error() -> ApiErrorModel:
    return ApiErrorModel(
        code="SYSTEM_INTERNAL_ERROR",
        category="system",
        httpStatus=500,
        message="服务暂时不可用",
    )


def _arguments(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        return {"input": cast(JsonValue, value)}
    return cast(dict[str, JsonValue], value)


def _provided_arguments(arguments: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {key: "[provided]" for key in arguments}
