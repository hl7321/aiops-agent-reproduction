import pytest

from super_ai.chat_configuration.tools import SkillNotAvailableError, create_load_skill_tool
from super_ai.tenancy.context import CurrentUser


class FakeLoader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def load_content(self, owner_user_id: str, normalized_name: str) -> str | None:
        self.calls.append((owner_user_id, normalized_name))
        if owner_user_id == "user-a" and normalized_name == "knowledge-search":
            return "SKILL_BODY_SENTINEL"
        return None


async def test_load_skill_is_lazy_owner_bound_and_normalizes_name() -> None:
    loader = FakeLoader()
    tool = create_load_skill_tool(CurrentUser("user-a"), {"knowledge-search"}, loader)
    assert loader.calls == []
    result = await tool.ainvoke({"name": "Knowledge Search"})
    assert result == {"name": "knowledge-search", "content": "SKILL_BODY_SENTINEL"}
    assert loader.calls == [("user-a", "knowledge-search")]


async def test_load_skill_rejects_unselected_before_repository_read() -> None:
    loader = FakeLoader()
    tool = create_load_skill_tool(CurrentUser("user-a"), {"knowledge-search"}, loader)
    with pytest.raises(SkillNotAvailableError):
        await tool.ainvoke({"name": "other-skill"})
    assert loader.calls == []


async def test_load_skill_rejects_deleted_or_cross_owner_content() -> None:
    loader = FakeLoader()
    tool = create_load_skill_tool(CurrentUser("user-b"), {"knowledge-search"}, loader)
    with pytest.raises(SkillNotAvailableError):
        await tool.ainvoke({"name": "knowledge-search"})
    assert loader.calls == [("user-b", "knowledge-search")]
