from datetime import datetime, timezone

from super_ai.api_contracts import KnowledgeRetrievalToolInput, KnowledgeRetrievalToolOutput
from super_ai.chat.agent_tools import create_agent_tools
from super_ai.tenancy.context import CurrentUser


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[CurrentUser, KnowledgeRetrievalToolInput]] = []

    async def retrieve(
        self, current_user: CurrentUser, tool_input: KnowledgeRetrievalToolInput
    ) -> KnowledgeRetrievalToolOutput:
        self.calls.append((current_user, tool_input))
        return KnowledgeRetrievalToolOutput(results=[])


async def test_tool_factory_is_lazy_and_binds_current_tenant() -> None:
    retriever = FakeRetriever()
    current_user = CurrentUser("user-a")

    tools = create_agent_tools(
        current_user,
        retriever,
        now=lambda: datetime(2026, 8, 18, 8, 30, tzinfo=timezone.utc),
    )

    assert [tool.name for tool in tools] == ["knowledge_retrieval", "get_current_time"]
    assert retriever.calls == []
    result = await tools[0].ainvoke({"query": "订单服务", "knowledgeBaseIds": ["kb-other"]})
    assert result == {"results": []}
    assert retriever.calls[0][0] == current_user
    assert retriever.calls[0][1].knowledge_base_ids == ("kb-other",)


async def test_current_time_tool_returns_timezone_aware_iso_timestamp() -> None:
    tools = create_agent_tools(
        CurrentUser("user-a"),
        FakeRetriever(),
        now=lambda: datetime(2026, 8, 18, 16, 30, tzinfo=timezone.utc),
    )

    result = await tools[1].ainvoke({})

    assert result == {"currentTime": "2026-08-18T16:30:00Z"}
