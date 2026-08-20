import pytest
from langchain_core.messages import AIMessage

from super_ai.chat.memory.summarizer import LangChainChatMemorySummarizer


class FakeModel:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[object] = []

    async def ainvoke(self, value: object) -> object:
        self.calls.append(value)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


async def test_summarizer_generates_incremental_nonempty_summary() -> None:
    model = FakeModel(AIMessage(content="新摘要"))
    summarizer = LangChainChatMemorySummarizer(model)  # type: ignore[arg-type]

    result = await summarizer.summarize("旧摘要", ("user: 问题", "assistant: 回答"))

    assert result == "新摘要"
    assert len(model.calls) == 1
    assert "旧摘要" in str(model.calls[0])


async def test_summarizer_rejects_empty_model_output() -> None:
    summarizer = LangChainChatMemorySummarizer(FakeModel(AIMessage(content="  ")))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="摘要模型未返回内容"):
        await summarizer.summarize(None, ("user: 问题", "assistant: 回答"))
