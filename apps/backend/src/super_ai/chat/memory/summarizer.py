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
                        "你负责压缩聊天历史，只返回新的中文摘要。必须严格使用以下六个 Markdown "
                        "二级标题，按顺序输出，不要增删或改名：\n"
                        "## 对话目标\n"
                        "## 关键事实与标识\n"
                        "## 已做决定\n"
                        "## 工具与证据\n"
                        "## 未解决事项\n"
                        "## 风险与注意事项\n"
                        "每节用 1-3 条短 bullet；没有内容写「（无）」。保留服务、告警、"
                        "incident_id/trace_id、时间、工具结论、引用标识、未完成事项与风险；"
                        "不得编造事实或引用。"
                    )
                ),
                HumanMessage(content=f"既有摘要：\n{previous}\n\n新增完整轮次：\n{transcript}"),
            ]
        )
        content = response.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("摘要模型未返回内容")
        return content.strip()
