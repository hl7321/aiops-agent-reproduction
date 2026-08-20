"""从不可变聊天记录中定位完整 user/assistant turn。"""

from dataclasses import dataclass

from super_ai.chat.models import ChatMessageRecord


@dataclass(frozen=True, slots=True)
class CompleteTurnBoundary:
    sequence: int
    complete_turn_count: int
    messages: tuple[ChatMessageRecord, ...]


def complete_turn_boundary(
    messages: tuple[ChatMessageRecord, ...], *, after_sequence: int
) -> CompleteTurnBoundary | None:
    scoped = tuple(item for item in messages if item.sequence > after_sequence)
    waiting_for_assistant = False
    complete_turn_count = 0
    boundary: int | None = None
    for item in scoped:
        if item.role == "user":
            waiting_for_assistant = True
        elif item.role == "assistant" and waiting_for_assistant:
            complete_turn_count += 1
            boundary = item.sequence
            waiting_for_assistant = False
    if boundary is None:
        return None
    return CompleteTurnBoundary(
        sequence=boundary,
        complete_turn_count=complete_turn_count,
        messages=tuple(item for item in scoped if item.sequence <= boundary),
    )
