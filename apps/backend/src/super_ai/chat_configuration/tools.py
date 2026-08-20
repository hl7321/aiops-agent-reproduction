from typing import Protocol

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from super_ai.chat_configuration.parser import SkillDocumentValidationError, normalize_skill_name
from super_ai.tenancy.context import CurrentUser


class SkillContentLoader(Protocol):
    async def load_content(self, owner_user_id: str, normalized_name: str) -> str | None: ...


class SkillNotAvailableError(RuntimeError):
    """Skill 不在本轮白名单或当前 owner 中不可见。"""


class _LoadSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)


def create_load_skill_tool(
    current_user: CurrentUser,
    allowed_names: set[str] | frozenset[str],
    loader: SkillContentLoader,
) -> BaseTool:
    allowed = frozenset(allowed_names)

    async def load_skill(name: str) -> dict[str, str]:
        try:
            normalized = normalize_skill_name(name)
        except SkillDocumentValidationError as error:
            raise SkillNotAvailableError("请求的 Skill 当前不可用") from error
        if normalized not in allowed:
            raise SkillNotAvailableError("请求的 Skill 当前不可用")
        content = await loader.load_content(current_user.owner_user_id, normalized)
        if content is None:
            raise SkillNotAvailableError("请求的 Skill 当前不可用")
        return {"name": normalized, "content": content}

    return StructuredTool.from_function(
        coroutine=load_skill,
        name="load_skill",
        description="按名称加载本轮已选择的 Agent Skill 完整正文；只在摘要显示需要时调用。",
        args_schema=_LoadSkillInput,
    )
