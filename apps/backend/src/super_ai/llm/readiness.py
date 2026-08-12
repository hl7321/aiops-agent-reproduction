"""模型 provider readiness 的安全返回 record。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderCapability = Literal["chat", "embedding", "rerank"]


class ProviderReadiness(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    provider: str
    model: str
    base_url: str = Field(alias="baseUrl")
    latency: float = Field(ge=0)
