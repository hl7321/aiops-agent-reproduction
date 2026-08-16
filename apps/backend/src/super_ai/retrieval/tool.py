from __future__ import annotations

from typing import Protocol

from langchain_core.tools import StructuredTool, ToolException

from super_ai.api_contracts import KnowledgeRetrievalToolInput, KnowledgeRetrievalToolOutput
from super_ai.retrieval.errors import KnowledgeRetrievalError
from super_ai.tenancy.context import CurrentUser


class KnowledgeRetriever(Protocol):
    async def retrieve(
        self, current_user: CurrentUser, tool_input: KnowledgeRetrievalToolInput
    ) -> KnowledgeRetrievalToolOutput: ...


def create_knowledge_retrieval_tool(
    current_user: CurrentUser, service: KnowledgeRetriever
) -> StructuredTool:
    async def retrieve(**values: object) -> dict[str, object]:
        tool_input = KnowledgeRetrievalToolInput.model_validate(values)
        try:
            output = await service.retrieve(current_user, tool_input)
        except KnowledgeRetrievalError as error:
            raise ToolException(str(error)) from error
        return output.model_dump(by_alias=True)

    return StructuredTool.from_function(
        coroutine=retrieve,
        name="knowledge_retrieval",
        description=(
            "在当前用户允许的知识文档中执行 BM25L 与向量混合检索，并返回经 Qwen "
            "rerank 的可追溯引用。"
        ),
        args_schema=KnowledgeRetrievalToolInput,
    )
