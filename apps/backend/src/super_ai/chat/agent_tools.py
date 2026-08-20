"""运行期绑定 CurrentUser 的初始 Agent 工具集。"""

from collections.abc import Callable
from datetime import datetime, timezone

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict

from super_ai.retrieval.tool import KnowledgeRetriever, create_knowledge_retrieval_tool
from super_ai.tenancy.context import CurrentUser


class _CurrentTimeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def create_agent_tools(
    current_user: CurrentUser,
    retrieval_service: KnowledgeRetriever,
    *,
    now: Callable[[], datetime],
) -> list[BaseTool]:
    async def get_current_time() -> dict[str, str]:
        current = now()
        if current.tzinfo is None:
            raise ValueError("当前时间必须包含时区")
        timestamp = current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"currentTime": timestamp}

    time_tool = StructuredTool.from_function(
        coroutine=get_current_time,
        name="get_current_time",
        description="返回当前带时区的 ISO 8601 时间。",
        args_schema=_CurrentTimeInput,
    )
    return [create_knowledge_retrieval_tool(current_user, retrieval_service), time_tool]
