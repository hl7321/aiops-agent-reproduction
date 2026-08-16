import pytest
from pydantic import ValidationError

from super_ai.api_contracts import KnowledgeRetrievalToolInput, KnowledgeRetrievalToolOutput
from super_ai.retrieval.tool import create_knowledge_retrieval_tool
from super_ai.tenancy.context import CurrentUser


class RecordingService:
    def __init__(self) -> None:
        self.users: list[CurrentUser] = []
        self.inputs: list[KnowledgeRetrievalToolInput] = []

    async def retrieve(
        self, current_user: CurrentUser, tool_input: KnowledgeRetrievalToolInput
    ) -> KnowledgeRetrievalToolOutput:
        self.users.append(current_user)
        self.inputs.append(tool_input)
        return KnowledgeRetrievalToolOutput(results=[])


async def test_tool_has_stable_schema_and_captures_current_user_outside_model_input() -> None:
    service = RecordingService()
    current_user = CurrentUser("user-a")
    tool = create_knowledge_retrieval_tool(current_user, service)

    output = await tool.ainvoke({"query": "订单服务", "topK": 3})

    assert tool.name == "knowledge_retrieval"
    assert set(tool.args) == {"query", "topK", "knowledgeBaseIds", "documentIds"}
    assert "ownerUserId" not in tool.args and "tenantId" not in tool.args
    assert output == {"results": []}
    assert service.users == [current_user]
    assert service.inputs[0].top_k == 3


async def test_invalid_tool_input_never_reaches_owner_bound_service() -> None:
    service = RecordingService()
    tool = create_knowledge_retrieval_tool(CurrentUser("user-a"), service)

    with pytest.raises(ValidationError):
        await tool.ainvoke({"query": "   ", "topK": 6})

    assert service.users == []
    assert service.inputs == []
