import asyncio
from collections.abc import Mapping

import pytest
from langchain_core.tools import BaseTool, tool

from super_ai.api_responses import AppError
from super_ai.mcp_connections.gateway import LangChainMcpToolGateway, McpClient
from super_ai.mcp_connections.models import McpConnectionTarget


@tool
def query_logs(query: str) -> str:
    """查询日志。"""
    return query


@tool
def get_alerts(service: str) -> str:
    """查询告警。"""
    return service


class FakeClient:
    def __init__(self, outcomes: list[list[BaseTool] | Exception]) -> None:
        self.outcomes = outcomes
        self.attempts = 0

    async def get_tools(self, *, server_name: str | None = None) -> list[BaseTool]:
        del server_name
        outcome = self.outcomes[self.attempts]
        self.attempts += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeFactory:
    def __init__(self, clients: Mapping[str, McpClient]) -> None:
        self.clients = clients
        self.created: list[str] = []

    def create(self, target: McpConnectionTarget) -> McpClient:
        self.created.append(target.id)
        return self.clients[target.id]


def target(identifier: str, *, retries: int = 0, timeout: int = 1) -> McpConnectionTarget:
    return McpConnectionTarget(
        identifier, identifier, "streamable_http", "https://example.test/mcp", timeout, retries
    )


async def test_gateway_retries_discovery_exactly_and_returns_one_tool_set() -> None:
    client = FakeClient([RuntimeError("first"), RuntimeError("second"), [query_logs]])
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    gateway = LangChainMcpToolGateway(FakeFactory({"one": client}), sleep=sleep)
    result = await gateway.discover((target("one", retries=2),), builtin_tool_names=frozenset())

    assert client.attempts == 3
    assert sleeps == [0.1, 0.2]
    assert [item.name for item in result.tools] == ["query_logs"]
    assert result.mcp_tool_names == frozenset({"query_logs"})


async def test_gateway_discovers_servers_concurrently() -> None:
    started = 0
    both_started = asyncio.Event()

    class BlockingClient:
        def __init__(self, returned: BaseTool) -> None:
            self.returned = returned

        async def get_tools(self, *, server_name: str | None = None) -> list[BaseTool]:
            nonlocal started
            del server_name
            started += 1
            if started == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.5)
            return [self.returned]

    factory = FakeFactory({"one": BlockingClient(query_logs), "two": BlockingClient(get_alerts)})
    result = await LangChainMcpToolGateway(factory).discover(
        (target("one"), target("two")), builtin_tool_names=frozenset()
    )
    assert {item.name for item in result.tools} == {"query_logs", "get_alerts"}


@pytest.mark.parametrize(
    "builtin", [frozenset[str](), frozenset[str]({"query_logs"})]
)
async def test_gateway_rejects_mcp_and_global_name_conflicts(builtin: frozenset[str]) -> None:
    clients = {"one": FakeClient([[query_logs]]), "two": FakeClient([[query_logs]])}
    targets = (target("one"), target("two")) if not builtin else (target("one"),)

    with pytest.raises(AppError) as captured:
        await LangChainMcpToolGateway(FakeFactory(clients)).discover(
            targets, builtin_tool_names=builtin
        )

    assert captured.value.code == "BUSINESS_MCP_TOOL_NAME_CONFLICT"
    assert captured.value.details == {"toolName": "query_logs"}


async def test_gateway_redacts_connection_failure() -> None:
    secret = "secret-in-query"
    failing = FakeClient([RuntimeError(f"https://example.test/mcp?token={secret}")])
    with pytest.raises(AppError) as captured:
        await LangChainMcpToolGateway(FakeFactory({"one": failing})).discover(
            (target("one"),), builtin_tool_names=frozenset()
        )
    assert captured.value.code == "SYSTEM_MCP_CONNECTION_FAILED"
    assert secret not in captured.value.safe_message


def test_gateway_does_not_create_clients_for_empty_targets() -> None:
    factory = FakeFactory({})
    gateway = LangChainMcpToolGateway(factory)
    assert asyncio.run(gateway.discover((), builtin_tool_names=frozenset())).tools == ()
    assert factory.created == []


async def test_discovered_tool_invocation_is_not_wrapped_in_automatic_retry() -> None:
    invocations = 0

    @tool
    def mutating_tool(value: str) -> str:
        """执行一次外部变更。"""
        nonlocal invocations
        invocations += 1
        raise RuntimeError(value)

    gateway = LangChainMcpToolGateway(FakeFactory({"one": FakeClient([[mutating_tool]])}))
    discovered = await gateway.discover(
        (target("one", retries=5),), builtin_tool_names=frozenset()
    )
    with pytest.raises(RuntimeError):
        await discovered.tools[0].ainvoke({"value": "fail"})
    assert invocations == 1
