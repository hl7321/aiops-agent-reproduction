"""运行时交付探针的 Pydantic 合同。"""

from typing import Literal, TypeAlias

from pydantic import Field, field_validator

from super_ai.api_contracts import ContractModel
from super_ai.runtime.security import redact_text

RuntimeDependencyName: TypeAlias = Literal["sqlite", "milvus", "qwen", "mcp"]
RuntimeDependencyStatus: TypeAlias = Literal["ready", "unavailable"]


class RuntimeDependencyResult(ContractModel):
    name: RuntimeDependencyName
    status: RuntimeDependencyStatus
    latency_ms: float = Field(alias="latencyMs", ge=0)
    error: str | None = None

    @field_validator("error")
    @classmethod
    def _redact_error(cls, value: str | None) -> str | None:
        return redact_text(value) if value else None


class RuntimeDependencies(ContractModel):
    sqlite: RuntimeDependencyResult
    milvus: RuntimeDependencyResult
    qwen: RuntimeDependencyResult
    mcp: RuntimeDependencyResult

    @property
    def ready(self) -> bool:
        return all(
            item.status == "ready"
            for item in (self.sqlite, self.milvus, self.qwen, self.mcp)
        )


class ReadinessData(ContractModel):
    status: RuntimeDependencyStatus
    dependencies: RuntimeDependencies


class ConfigurationStatus(ContractModel):
    status: Literal["valid", "invalid"]
    sections: list[str]
    error: str | None = None


class ConfigurationCheckData(ContractModel):
    status: Literal["ready", "configuration_invalid", "dependencies_unavailable"]
    configuration: ConfigurationStatus
    dependencies: RuntimeDependencies | None


class ProcessMetrics(ContractModel):
    scope: Literal["process"] = "process"
    request_count: int = Field(alias="requestCount", ge=0)
    failure_count: int = Field(alias="failureCount", ge=0)
    total_duration_ms: float = Field(alias="totalDurationMs", ge=0)
    average_duration_ms: float = Field(alias="averageDurationMs", ge=0)
