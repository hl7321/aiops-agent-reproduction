"""显式、可注入的聊天历史摘要器。"""

from collections.abc import Sequence
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


class ChatMemorySummarizer(Protocol):
    async def summarize(
        self, previous_summary: str | None, messages: Sequence[str]
    ) -> str: ...


class LangChainChatMemorySummarizer:
    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def summarize(self, previous_summary: str | None, messages: Sequence[str]) -> str:
        previous = previous_summary or "（无既有摘要）"
        transcript = "\n".join(messages)
        response = await self._model.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你负责压缩聊天历史。保留关键事实、决定、未解决事项、工具结论与引用标识；"
                        "不得编造事实，只返回新的中文摘要。"
                    )
                ),
                HumanMessage(content=f"既有摘要：\n{previous}\n\n新增完整轮次：\n{transcript}"),
            ]
        )
        content = response.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("摘要模型未返回内容")
        return content.strip()
