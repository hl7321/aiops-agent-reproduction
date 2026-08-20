from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

from super_ai.api_contracts import SseEvent, ToolCallEvent
from super_ai.chat.agent_events import AgentEventMapper, TurnContext
from super_ai.chat.agent_runner import AgentChatRunner
from super_ai.tenancy.context import CurrentUser

NOW = datetime(2026, 8, 18, tzinfo=timezone.utc)


class FakeAgent:
    def __init__(self, events: Sequence[dict[str, Any]]) -> None:
        self.events = events
        self.inputs: list[dict[str, object]] = []

    async def astream_events(
        self, value: dict[str, object], *, version: str
    ) -> AsyncIterator[dict[str, Any]]:
        self.inputs.append(value)
        assert version == "v2"
        for event in self.events:
            yield event


class RecordingFactory:
    def __init__(self, agent: FakeAgent) -> None:
        self.agent = agent
        self.calls: list[tuple[BaseChatModel, Sequence[BaseTool], str]] = []

    def __call__(
        self, model: BaseChatModel, tools: Sequence[BaseTool], system_prompt: str
    ) -> FakeAgent:
        self.calls.append((model, tools, system_prompt))
        return self.agent


class DummyChatModel:
    pass


def _runner(events: Sequence[dict[str, Any]], tools: Sequence[BaseTool] = ()):
    agent = FakeAgent(events)
    factory = RecordingFactory(agent)
    mapper = AgentEventMapper(TurnContext(turn_id="turn-1", now=lambda: NOW))
    emitted: list[SseEvent] = []

    async def emit(event: SseEvent) -> None:
        emitted.append(event)

    runner = AgentChatRunner(
        model=DummyChatModel(),  # type: ignore[arg-type]
        tools=tools,
        mapper=mapper,
        agent_factory=factory,
        emit=emit,
    )
    return runner, factory, emitted


class RecordingAuditor:
    def __init__(self) -> None:
        self.lifecycle: list[tuple[str, str]] = []
        self.arguments: list[dict[str, object]] = []
        self.errors: list[str] = []

    async def start_tool(self, current_user: CurrentUser, **values: object) -> None:
        self.lifecycle.append(("started", str(values["tool_call_id"])))
        self.arguments.append(values["arguments"])  # type: ignore[arg-type]

    async def complete_tool(self, current_user: CurrentUser, tool_call_id: str) -> None:
        self.lifecycle.append(("completed", tool_call_id))

    async def fail_tool(
        self, current_user: CurrentUser, tool_call_id: str, **values: object
    ) -> None:
        self.lifecycle.append(("failed", tool_call_id))
        self.errors.append(str(values["error"]))


async def test_runner_returns_final_model_text_without_forcing_a_tool() -> None:
    runner, factory, emitted = _runner(
        [
            {
                "event": "on_chat_model_stream",
                "run_id": "model-final",
                "data": {"chunk": AIMessageChunk(content="你")},
            },
            {
                "event": "on_chat_model_stream",
                "run_id": "model-final",
                "data": {"chunk": AIMessageChunk(content="好")},
            },
        ]
    )

    result = await runner.run([HumanMessage(content="问候")])

    assert result.final_text == "你好"
    assert result.references == ()
    assert result.tool_call_ids == ()
    assert emitted == []
    assert len(factory.calls) == 1
    assert factory.agent.inputs == [{"messages": [HumanMessage(content="问候")]}]


async def test_runner_passes_request_specific_system_prompt_to_agent_factory() -> None:
    agent = FakeAgent(
        [
            {
                "event": "on_chat_model_stream",
                "run_id": "model-final",
                "data": {"chunk": AIMessageChunk(content="完成")},
            }
        ]
    )
    factory = RecordingFactory(agent)
    mapper = AgentEventMapper(TurnContext(turn_id="turn-prompt", now=lambda: NOW))

    async def emit(event: SseEvent) -> None:
        return None

    runner = AgentChatRunner(
        model=DummyChatModel(),  # type: ignore[arg-type]
        tools=(),
        system_prompt="PLATFORM + USER + SKILL_SUMMARIES",
        mapper=mapper,
        agent_factory=factory,
        emit=emit,
    )
    await runner.run([HumanMessage(content="开始")])

    assert factory.calls[0][2] == "PLATFORM + USER + SKILL_SUMMARIES"


async def test_runner_maps_real_reasoning_tool_lifecycle_and_references() -> None:
    citation: dict[str, object] = {
        "chunkId": "chunk-1",
        "documentId": "doc-1",
        "knowledgeBaseId": "kb-1",
        "source": "runbook.md",
        "excerpt": "重启订单服务",
        "metadata": {},
        "vectorRank": 1,
        "vectorScore": 0.9,
        "bm25Rank": None,
        "bm25Score": None,
        "rrfScore": 1 / 61,
        "rerankRank": 1,
        "rerankScore": 0.8,
        "score": 0.8,
    }
    runner, _, emitted = _runner(
        [
            {
                "event": "on_chat_model_stream",
                "run_id": "model-plan",
                "data": {
                    "chunk": AIMessageChunk(
                        content="", additional_kwargs={"reasoning_content": "需要检索"}
                    )
                },
            },
            {
                "event": "on_tool_start",
                "run_id": "call-1",
                "name": "knowledge_retrieval",
                "data": {"input": {"query": "订单服务"}},
            },
            {
                "event": "on_tool_end",
                "run_id": "call-1",
                "name": "knowledge_retrieval",
                "data": {"output": {"results": [citation]}},
            },
            {
                "event": "on_chat_model_stream",
                "run_id": "model-final",
                "data": {"chunk": AIMessageChunk(content="请重启订单服务")},
            },
        ]
    )

    result = await runner.run([HumanMessage(content="如何处理？")])

    assert result.final_text == "请重启订单服务"
    assert result.tool_call_ids == ("call-1",)
    assert result.references[0].chunk_id == "chunk-1"
    assert [event.type for event in emitted] == [
        "reasoning.delta",
        "tool.call",
        "tool.call",
        "reference.source",
    ]
    tool_events = [event for event in emitted if isinstance(event, ToolCallEvent)]
    assert [event.data.lifecycle for event in tool_events] == ["started", "completed"]


async def test_runner_emits_failed_tool_event_and_does_not_return_fake_answer() -> None:
    runner, _, emitted = _runner(
        [
            {
                "event": "on_tool_start",
                "run_id": "call-failed",
                "name": "knowledge_retrieval",
                "data": {"input": {"query": "订单服务"}},
            },
            {
                "event": "on_tool_error",
                "run_id": "call-failed",
                "name": "knowledge_retrieval",
                "data": {"error": RuntimeError("provider unavailable")},
            },
        ]
    )

    result = await runner.run([HumanMessage(content="如何处理？")])

    assert result.final_text == ""
    tool_events = [event for event in emitted if isinstance(event, ToolCallEvent)]
    assert [event.data.lifecycle for event in tool_events] == ["started", "failed"]


async def test_runner_audits_framework_tool_lifecycle_with_same_tool_call_id() -> None:
    events: list[dict[str, Any]] = [
        {
            "event": "on_tool_start",
            "run_id": "call-audit",
            "name": "get_current_time",
            "data": {"input": {}},
        },
        {
            "event": "on_tool_end",
            "run_id": "call-audit",
            "name": "get_current_time",
            "data": {"output": {"currentTime": "2026-08-18T00:00:00Z"}},
        },
        {
            "event": "on_chat_model_stream",
            "run_id": "model-final",
            "data": {"chunk": AIMessageChunk(content="现在是午夜")},
        },
    ]
    agent = FakeAgent(events)
    factory = RecordingFactory(agent)
    auditor = RecordingAuditor()
    mapper = AgentEventMapper(TurnContext(turn_id="turn-audit", now=lambda: NOW))

    async def emit(event: SseEvent) -> None:
        return None

    runner = AgentChatRunner(
        model=DummyChatModel(),  # type: ignore[arg-type]
        tools=(),
        mapper=mapper,
        agent_factory=factory,
        emit=emit,
        auditor=auditor,
        current_user=CurrentUser("user-a"),
        chat_session_id="session-a",
    )

    result = await runner.run([HumanMessage(content="现在几点？")])

    assert result.tool_call_ids == ("call-audit",)
    assert auditor.lifecycle == [("started", "call-audit"), ("completed", "call-audit")]


async def test_runner_normalizes_langchain_tool_message_output() -> None:
    runner, _, emitted = _runner(
        [
            {
                "event": "on_tool_end",
                "run_id": "call-time",
                "name": "get_current_time",
                "data": {
                    "output": ToolMessage(
                        content='{"currentTime":"2026-08-18T00:00:00Z"}',
                        tool_call_id="provider-call-time",
                    )
                },
            },
            {
                "event": "on_chat_model_stream",
                "run_id": "model-final",
                "data": {"chunk": AIMessageChunk(content="现在是午夜")},
            },
        ]
    )

    result = await runner.run([HumanMessage(content="现在几点？")])

    assert result.final_text == "现在是午夜"
    tool_event = next(event for event in emitted if isinstance(event, ToolCallEvent))
    assert tool_event.data.output == {"currentTime": "2026-08-18T00:00:00Z"}


async def test_runner_redacts_mcp_arguments_and_output_from_sse_and_audit() -> None:
    sentinel = "MCP_ARGUMENT_SECRET"
    events: list[dict[str, Any]] = [
        {
            "event": "on_tool_start",
            "run_id": "call-mcp",
            "name": "query_logs",
            "data": {"input": {"query": sentinel, "limit": 5}},
        },
        {
            "event": "on_tool_end",
            "run_id": "call-mcp",
            "name": "query_logs",
            "data": {"output": {"rows": [sentinel]}},
        },
        {
            "event": "on_chat_model_stream",
            "run_id": "model-final",
            "data": {"chunk": AIMessageChunk(content="完成")},
        },
    ]
    agent = FakeAgent(events)
    factory = RecordingFactory(agent)
    auditor = RecordingAuditor()
    emitted: list[SseEvent] = []

    async def emit(event: SseEvent) -> None:
        emitted.append(event)

    runner = AgentChatRunner(
        model=DummyChatModel(),  # type: ignore[arg-type]
        tools=(),
        mapper=AgentEventMapper(TurnContext("turn-mcp", lambda: NOW)),
        agent_factory=factory,
        emit=emit,
        auditor=auditor,
        current_user=CurrentUser("user-a"),
        chat_session_id="session-a",
        sensitive_tool_names=frozenset({"query_logs"}),
    )
    await runner.run([HumanMessage(content="查日志")])

    serialized = "".join(event.model_dump_json() for event in emitted)
    assert sentinel not in serialized
    assert auditor.arguments == [{"query": "[provided]", "limit": "[provided]"}]
    tool_events = [event for event in emitted if isinstance(event, ToolCallEvent)]
    assert tool_events[0].data.input == {"query": "[provided]", "limit": "[provided]"}
    assert tool_events[1].data.output == {"status": "completed"}


async def test_runner_redacts_mcp_failure_before_audit() -> None:
    sentinel = "MCP_ERROR_SECRET"
    events: list[dict[str, Any]] = [
        {
            "event": "on_tool_start",
            "run_id": "call-mcp",
            "name": "query_logs",
            "data": {"input": {"query": sentinel}},
        },
        {
            "event": "on_tool_error",
            "run_id": "call-mcp",
            "name": "query_logs",
            "data": {"error": RuntimeError(f"https://example.test/mcp?token={sentinel}")},
        },
    ]
    auditor = RecordingAuditor()
    emitted: list[SseEvent] = []

    async def emit(event: SseEvent) -> None:
        emitted.append(event)

    runner = AgentChatRunner(
        model=DummyChatModel(),  # type: ignore[arg-type]
        tools=(),
        mapper=AgentEventMapper(TurnContext("turn-mcp-fail", lambda: NOW)),
        agent_factory=RecordingFactory(FakeAgent(events)),
        emit=emit,
        auditor=auditor,
        current_user=CurrentUser("user-a"),
        chat_session_id="session-a",
        sensitive_tool_names=frozenset({"query_logs"}),
    )
    await runner.run([HumanMessage(content="查日志")])

    assert auditor.errors == ["MCP 工具调用失败"]
    assert sentinel not in "".join(event.model_dump_json() for event in emitted)
