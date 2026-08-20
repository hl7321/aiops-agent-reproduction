from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from super_ai.mcp_connections.models import McpTransport
from super_ai.mcp_connections.security import validate_mcp_url
from super_ai.project_config import ProjectConfigError, load_project_config


class ClsMcpServerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    base_url: str = Field(default="", alias="baseUrl")
    transport: McpTransport = "streamable_http"
    timeout_seconds: int = Field(default=30, alias="timeoutSeconds", ge=1, le=300)
    retries: int = Field(default=1, ge=0, le=5)

    @field_validator("base_url")
    @classmethod
    def validate_optional_url(cls, value: str) -> str:
        return validate_mcp_url(value) if value.strip() else ""


def load_cls_mcp_server_settings(project_path: Path, user_path: Path) -> ClsMcpServerSettings:
    merged = load_project_config(project_path, user_path)
    raw = merged.get("clsMcpServer")
    candidate = raw if isinstance(raw, dict) else {}
    allowed = {
        key: candidate[key]
        for key in ("baseUrl", "transport", "timeoutSeconds", "retries")
        if key in candidate
    }
    try:
        return ClsMcpServerSettings.model_validate(allowed)
    except ValidationError as error:
        raise ProjectConfigError("clsMcpServer 配置校验失败") from error
