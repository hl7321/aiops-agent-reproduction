from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from super_ai.chat.agent_events import AgentEventMapper, TurnContext
from super_ai.chat.agent_runner import AgentRunResult
from super_ai.chat_configuration.agent import ConfiguredAgentTurnRunner
from super_ai.chat_configuration.assembly import ChatAgentConfigurationSnapshot
from super_ai.tenancy.context import CurrentUser


@tool
def query_logs(query: str) -> str:
    """查询真实日志。"""
    return query


class DummyStore:
    async def load_content(self, owner_user_id: str, normalized_name: str) -> str | None:
        del owner_user_id, normalized_name
        return None


class DummyAuditor:
    pass


async def test_configured_chat_injects_mcp_tool_without_preinvoking_it(
    monkeypatch: Any,
) -> None:
    captured: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, **values: object) -> None:
            captured.update(values)

        async def run(self, messages: object) -> AgentRunResult:
            del messages
            return AgentRunResult("完成", (), ())

    monkeypatch.setattr("super_ai.chat_configuration.agent.AgentChatRunner", FakeRunner)
    runner = ConfiguredAgentTurnRunner(
        current_user=CurrentUser("user-a"),
        session_id="session-a",
        model=object(),  # type: ignore[arg-type]
        base_tools=(query_logs,),
        configuration_store=DummyStore(),  # type: ignore[arg-type]
        configuration=ChatAgentConfigurationSnapshot(user_prompt=None, skills=()),
        mapper=AgentEventMapper(
            TurnContext("turn-a", lambda: datetime.now(timezone.utc))
        ),
        emit=_ignore_event,
        auditor=DummyAuditor(),  # type: ignore[arg-type]
        mcp_tool_names=frozenset({"query_logs"}),
    )

    result = await runner.run([HumanMessage(content="无需查日志")])

    assert result.final_text == "完成"
    assert {item.name for item in captured["tools"]} == {  # type: ignore[union-attr]
        "query_logs",
        "load_skill",
    }
    assert captured["sensitive_tool_names"] == frozenset({"query_logs"})


async def _ignore_event(_event: object) -> None:
    return None
