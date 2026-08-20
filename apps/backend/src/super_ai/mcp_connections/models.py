from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

McpTransport: TypeAlias = Literal["sse", "streamable_http"]


@dataclass(frozen=True, slots=True)
class McpDiscoveredToolRecord:
    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class CreateMcpConnection:
    name: str
    transport: McpTransport
    url: str
    enabled: bool
    timeout_seconds: int
    retries: int


@dataclass(frozen=True, slots=True)
class McpConnectionRecord:
    id: str
    owner_user_id: str
    name: str
    transport: McpTransport
    url: str
    enabled: bool
    timeout_seconds: int
    retries: int
    last_check: datetime | None
    last_error: str | None
    discovered_tools: tuple[McpDiscoveredToolRecord, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class McpConnectionTarget:
    id: str
    name: str
    transport: McpTransport
    url: str
    timeout_seconds: int
    retries: int

    @classmethod
    def from_record(cls, record: McpConnectionRecord) -> "McpConnectionTarget":
        return cls(
            record.id,
            record.name,
            record.transport,
            record.url,
            record.timeout_seconds,
            record.retries,
        )
