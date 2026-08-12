"""HTTP 与 SSE 共享合同的 Python/Pydantic 镜像。"""

from dataclasses import dataclass
from typing import Annotated, Final, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

ErrorCode: TypeAlias = Literal[
    "AUTH_REQUIRED",
    "AUTH_FORBIDDEN",
    "AUTH_INVALID_CREDENTIALS",
    "AUTH_EMAIL_ALREADY_REGISTERED",
    "BUSINESS_RULE_VIOLATION",
    "BUSINESS_RESOURCE_NOT_FOUND",
    "VALIDATION_REQUEST_INVALID",
    "SYSTEM_ROUTE_NOT_FOUND",
    "SYSTEM_METHOD_NOT_ALLOWED",
    "SYSTEM_INTERNAL_ERROR",
]
ErrorCategory: TypeAlias = Literal[
    "authentication",
    "authorization",
    "business",
    "validation",
    "system",
]
SseEventType: TypeAlias = Literal[
    "content.delta",
    "reasoning.delta",
    "tool.call",
    "reference.source",
    "task.status",
    "report",
    "complete",
    "error",
]
SseChannel: TypeAlias = Literal["chat", "aiops"]
ToolCallLifecycle: TypeAlias = Literal["started", "delta", "completed", "failed"]
TaskLifecycle: TypeAlias = Literal["queued", "running", "completed", "failed"]

SSE_EVENT_TYPES: Final[tuple[SseEventType, ...]] = (
    "content.delta",
    "reasoning.delta",
    "tool.call",
    "reference.source",
    "task.status",
    "report",
    "complete",
    "error",
)
TOOL_CALL_LIFECYCLES: Final[tuple[ToolCallLifecycle, ...]] = (
    "started",
    "delta",
    "completed",
    "failed",
)


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    """稳定错误目录中的一个定义。"""

    code: ErrorCode
    category: ErrorCategory
    http_status: int
    default_message: str

    def to_contract(self) -> dict[str, object]:
        """转换为与共享 manifest 一致的 JSON 形状。"""
        return {
            "code": self.code,
            "category": self.category,
            "httpStatus": self.http_status,
            "defaultMessage": self.default_message,
        }


ERROR_DEFINITIONS: Final[dict[ErrorCode, ErrorDefinition]] = {
    "AUTH_REQUIRED": ErrorDefinition(
        code="AUTH_REQUIRED",
        category="authentication",
        http_status=401,
        default_message="需要认证后才能访问",
    ),
    "AUTH_FORBIDDEN": ErrorDefinition(
        code="AUTH_FORBIDDEN",
        category="authorization",
        http_status=403,
        default_message="没有权限执行该操作",
    ),
    "AUTH_INVALID_CREDENTIALS": ErrorDefinition(
        code="AUTH_INVALID_CREDENTIALS",
        category="authentication",
        http_status=401,
        default_message="邮箱或密码错误",
    ),
    "AUTH_EMAIL_ALREADY_REGISTERED": ErrorDefinition(
        code="AUTH_EMAIL_ALREADY_REGISTERED",
        category="business",
        http_status=409,
        default_message="该邮箱已注册",
    ),
    "BUSINESS_RULE_VIOLATION": ErrorDefinition(
        code="BUSINESS_RULE_VIOLATION",
        category="business",
        http_status=409,
        default_message="请求与当前业务规则冲突",
    ),
    "BUSINESS_RESOURCE_NOT_FOUND": ErrorDefinition(
        code="BUSINESS_RESOURCE_NOT_FOUND",
        category="business",
        http_status=404,
        default_message="请求的资源不存在",
    ),
    "VALIDATION_REQUEST_INVALID": ErrorDefinition(
        code="VALIDATION_REQUEST_INVALID",
        category="validation",
        http_status=422,
        default_message="请求参数验证失败",
    ),
    "SYSTEM_ROUTE_NOT_FOUND": ErrorDefinition(
        code="SYSTEM_ROUTE_NOT_FOUND",
        category="system",
        http_status=404,
        default_message="请求的资源不存在",
    ),
    "SYSTEM_METHOD_NOT_ALLOWED": ErrorDefinition(
        code="SYSTEM_METHOD_NOT_ALLOWED",
        category="system",
        http_status=405,
        default_message="请求方法不受支持",
    ),
    "SYSTEM_INTERNAL_ERROR": ErrorDefinition(
        code="SYSTEM_INTERNAL_ERROR",
        category="system",
        http_status=500,
        default_message="服务暂时不可用",
    ),
}


class ContractModel(BaseModel):
    """为共享合同提供一致 alias 行为。"""

    model_config = ConfigDict(populate_by_name=True)


class RequestMeta(ContractModel):
    request_id: str = Field(alias="requestId")


class ApiErrorModel(ContractModel):
    code: ErrorCode
    category: ErrorCategory
    http_status: int = Field(alias="httpStatus")
    message: str
    details: JsonValue | None = None


T = TypeVar("T")


class SuccessEnvelope(ContractModel, Generic[T]):
    ok: Literal[True] = True
    data: T
    meta: RequestMeta


class FailureEnvelope(ContractModel):
    ok: Literal[False] = False
    error: ApiErrorModel
    meta: RequestMeta


class FoundationStatus(ContractModel):
    status: Literal["ok"] = "ok"


class AuthUser(ContractModel):
    id: str
    email: str
    created_at: str = Field(alias="createdAt")


class RegisterRequest(ContractModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LoginRequest(ContractModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LoginData(ContractModel):
    user: AuthUser
    token: str


class LogoutData(ContractModel):
    revoked: Literal[True] = True


class SseEventBase(ContractModel):
    id: str
    channel: SseChannel
    timestamp: str


class DeltaData(ContractModel):
    delta: str


class ContentDeltaEvent(SseEventBase):
    type: Literal["content.delta"] = "content.delta"
    data: DeltaData


class ReasoningDeltaEvent(SseEventBase):
    type: Literal["reasoning.delta"] = "reasoning.delta"
    data: DeltaData


class ToolCallData(ContractModel):
    tool_call_id: str = Field(alias="toolCallId")
    tool_name: str = Field(alias="toolName")
    lifecycle: ToolCallLifecycle
    input: JsonValue | None = None
    delta: str | None = None
    output: JsonValue | None = None
    error: ApiErrorModel | None = None


class ToolCallEvent(SseEventBase):
    type: Literal["tool.call"] = "tool.call"
    data: ToolCallData


class ReferenceSource(ContractModel):
    id: str
    title: str
    url: str | None = None


class ReferenceSourceData(ContractModel):
    source: ReferenceSource


class ReferenceSourceEvent(SseEventBase):
    type: Literal["reference.source"] = "reference.source"
    data: ReferenceSourceData


class TaskStatusData(ContractModel):
    task_id: str = Field(alias="taskId")
    status: TaskLifecycle
    message: str | None = None


class TaskStatusEvent(SseEventBase):
    type: Literal["task.status"] = "task.status"
    data: TaskStatusData


class ReportData(ContractModel):
    report: JsonValue


class ReportEvent(SseEventBase):
    type: Literal["report"] = "report"
    data: ReportData


class CompleteData(ContractModel):
    finish_reason: Literal["stop", "error", "cancelled"] = Field(alias="finishReason")


class CompleteEvent(SseEventBase):
    type: Literal["complete"] = "complete"
    data: CompleteData


class ErrorData(ContractModel):
    error: ApiErrorModel


class ErrorEvent(SseEventBase):
    type: Literal["error"] = "error"
    data: ErrorData


SseEvent: TypeAlias = Annotated[
    ContentDeltaEvent
    | ReasoningDeltaEvent
    | ToolCallEvent
    | ReferenceSourceEvent
    | TaskStatusEvent
    | ReportEvent
    | CompleteEvent
    | ErrorEvent,
    Field(discriminator="type"),
]
