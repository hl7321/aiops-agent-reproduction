"""Agent 运行事件到共享 SSE 合同的确定性映射。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, TypedDict

from super_ai.api_contracts import (
    ApiErrorModel,
    ChatReference,
    CompleteData,
    CompleteEvent,
    ContentDeltaEvent,
    DeltaData,
    ErrorData,
    ErrorEvent,
    ReasoningDeltaEvent,
    ReferenceSource,
    ReferenceSourceData,
    ReferenceSourceEvent,
    ToolCallData,
    ToolCallEvent,
    ToolCallLifecycle,
)
from super_ai.project_config import JsonValue


@dataclass(slots=True)
class TurnContext:
    turn_id: str
    now: Callable[[], datetime]
    _next_sequence: int = 1
    _references: list[ChatReference] = field(default_factory=lambda: list[ChatReference]())
    _tool_call_ids: list[str] = field(default_factory=lambda: list[str]())
    _terminated: bool = False

    @property
    def references(self) -> tuple[ChatReference, ...]:
        return tuple(self._references)

    @property
    def tool_call_ids(self) -> tuple[str, ...]:
        return tuple(self._tool_call_ids)

    def event_fields(self, *, terminal: bool = False) -> "_EventFields":
        if self._terminated:
            raise RuntimeError("当前 Agent turn 已经终结")
        sequence = self._next_sequence
        self._next_sequence += 1
        if terminal:
            self._terminated = True
        return {
            "id": f"{self.turn_id}:{sequence}",
            "sequence": sequence,
            "channel": "chat",
            "timestamp": _timestamp(self.now()),
        }

    def remember_tool_call(self, tool_call_id: str) -> None:
        if tool_call_id not in self._tool_call_ids:
            self._tool_call_ids.append(tool_call_id)

    def remember_reference(self, reference: ChatReference) -> None:
        if all(item.chunk_id != reference.chunk_id for item in self._references):
            self._references.append(reference)


class AgentEventMapper:
    def __init__(self, context: TurnContext) -> None:
        self._context = context

    @property
    def context(self) -> TurnContext:
        return self._context

    def reasoning(self, delta: str) -> ReasoningDeltaEvent:
        return ReasoningDeltaEvent(
            **self._context.event_fields(), data=DeltaData(delta=delta)
        )

    def tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
        lifecycle: ToolCallLifecycle,
        *,
        input: JsonValue | None = None,
        delta: str | None = None,
        output: JsonValue | None = None,
        error: ApiErrorModel | None = None,
    ) -> ToolCallEvent:
        self._context.remember_tool_call(tool_call_id)
        return ToolCallEvent(
            **self._context.event_fields(),
            data=ToolCallData(
                toolCallId=tool_call_id,
                toolName=tool_name,
                lifecycle=lifecycle,
                input=input,
                delta=delta,
                output=output,
                error=error,
            ),
        )

    def reference(self, reference: ChatReference) -> ReferenceSourceEvent:
        self._context.remember_reference(reference)
        return ReferenceSourceEvent(
            **self._context.event_fields(),
            data=ReferenceSourceData(
                source=ReferenceSource(id=reference.chunk_id, title=reference.source)
            ),
        )

    def content(self, text: str) -> list[ContentDeltaEvent]:
        return [
            ContentDeltaEvent(**self._context.event_fields(), data=DeltaData(delta=character))
            for character in text
        ]

    def complete(self) -> CompleteEvent:
        return CompleteEvent(
            **self._context.event_fields(terminal=True),
            data=CompleteData(finishReason="stop"),
        )

    def error(self, error: ApiErrorModel) -> ErrorEvent:
        return ErrorEvent(
            **self._context.event_fields(terminal=True), data=ErrorData(error=error)
        )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("SSE timestamp 必须包含时区")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class _EventFields(TypedDict):
    id: str
    sequence: int
    channel: Literal["chat"]
    timestamp: str
