"""将 owner-scoped 聊天历史裁剪并转换为 LangChain messages。"""

from collections.abc import Callable, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from super_ai.chat.models import ChatMessageRecord
from super_ai.llm.errors import ModelConfigurationError


def trim_chat_history(
    owner_user_id: str,
    messages: Sequence[ChatMessageRecord],
    *,
    context_window_tokens: int,
    reserved_tokens: int,
    count_tokens: Callable[[str], int],
) -> tuple[BaseMessage, ...]:
    if any(message.owner_user_id != owner_user_id for message in messages):
        raise ValueError("聊天历史包含 owner scope 之外的消息")
    if not messages:
        return ()
    available = context_window_tokens - reserved_tokens
    if available <= 0:
        raise ModelConfigurationError("模型上下文预算不足")
    newest_cost = count_tokens(messages[-1].content)
    if newest_cost < 0:
        raise ValueError("token counter 不得返回负数")
    if newest_cost > available:
        raise ModelConfigurationError("当前消息超过模型上下文预算")

    selected: list[ChatMessageRecord] = []
    used = 0
    for message in reversed(messages):
        cost = count_tokens(message.content)
        if cost < 0:
            raise ValueError("token counter 不得返回负数")
        if used + cost > available:
            break
        selected.append(message)
        used += cost
    return tuple(_to_langchain(message) for message in reversed(selected))


def _to_langchain(message: ChatMessageRecord) -> BaseMessage:
    if message.role == "user":
        return HumanMessage(content=message.content)
    if message.role == "assistant":
        return AIMessage(content=message.content)
    if message.role == "system":
        return SystemMessage(content=message.content)
    raw_ids = message.metadata.get("toolCallIds")
    tool_call_id = (
        raw_ids[0]
        if isinstance(raw_ids, list) and raw_ids and isinstance(raw_ids[0], str)
        else message.id
    )
    return ToolMessage(content=message.content, tool_call_id=tool_call_id)
