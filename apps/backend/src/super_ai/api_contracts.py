"""HTTP 与 SSE 共享合同的 Python/Pydantic 镜像。"""

from dataclasses import dataclass
from typing import Annotated, Final, Generic, Literal, TypeAlias, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

LANGCHAIN_TEXT_BLOCK_TYPE: Final = "text"
LANGCHAIN_ERROR_FIELD: Final = "error"

ErrorCode: TypeAlias = Literal[
    "AUTH_REQUIRED",
    "AUTH_FORBIDDEN",
    "AUTH_INVALID_CREDENTIALS",
    "AUTH_EMAIL_ALREADY_REGISTERED",
    "BUSINESS_RULE_VIOLATION",
    "BUSINESS_CONFLICT",
    "BUSINESS_RESOURCE_NOT_FOUND",
    "BUSINESS_MCP_TOOL_NAME_CONFLICT",
    "CHAT_CONTEXT_LIMIT_REACHED",
    "VALIDATION_REQUEST_INVALID",
    "SYSTEM_ROUTE_NOT_FOUND",
    "SYSTEM_METHOD_NOT_ALLOWED",
    "SYSTEM_INTERNAL_ERROR",
    "SYSTEM_MODEL_CAPABILITY_MISSING",
    "SYSTEM_MCP_CONNECTION_FAILED",
    "SYSTEM_ALERT_SOURCES_UNAVAILABLE",
    "SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE",
    "SYSTEM_UNAVAILABLE",
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
ChatMemoryMode: TypeAlias = Literal["every_30_turns", "context_70_percent", "manual"]
TaskLifecycle: TypeAlias = Literal["queued", "running", "succeeded", "failed", "cancelled"]
DiagnosticReplanAction: TypeAlias = Literal["continue", "replan", "report"]

SSE_TOOL_CALL_TYPE: Final[SseEventType] = "tool.call"
SSE_REFERENCE_SOURCE_TYPE: Final[SseEventType] = "reference.source"
SSE_TASK_STATUS_TYPE: Final[SseEventType] = "task.status"
SSE_REPORT_TYPE: Final[SseEventType] = "report"
SSE_COMPLETE_TYPE: Final[SseEventType] = "complete"
SSE_ERROR_TYPE: Final[SseEventType] = "error"
SSE_ERROR_DATA_KEY: Final = "error"
SSE_FINISH_REASON_ERROR: Final = "error"

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
KNOWLEDGE_UPLOAD_POLICY: Final[dict[str, object]] = {
    "maxBytes": 10 * 1024 * 1024,
    "allowedTypes": {".md": "text/markdown", ".pdf": "application/pdf"},
    "multipart": {
        "file": "file",
        "chunkingConfig": "chunkingConfig",
        "overwrite": "overwrite",
    },
    "strategies": ["fixed-character", "markdown-heading", "paragraph"],
}
CHAT_SKILL_UPLOAD_POLICY: Final[dict[str, object]] = {
    "multipart": {"file": "file"},
    "filename": "SKILL.md",
    "maxBytes": 256 * 1024,
    "maxNameCharacters": 64,
    "maxDescriptionCharacters": 500,
    "maxSummaryCharacters": 240,
    "normalizedNamePattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
}
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
    "BUSINESS_CONFLICT": ErrorDefinition(
        code="BUSINESS_CONFLICT",
        category="business",
        http_status=409,
        default_message="相同内容的文档已存在",
    ),
    "BUSINESS_RESOURCE_NOT_FOUND": ErrorDefinition(
        code="BUSINESS_RESOURCE_NOT_FOUND",
        category="business",
        http_status=404,
        default_message="请求的资源不存在",
    ),
    "BUSINESS_MCP_TOOL_NAME_CONFLICT": ErrorDefinition(
        code="BUSINESS_MCP_TOOL_NAME_CONFLICT",
        category="business",
        http_status=409,
        default_message="MCP 工具名称发生冲突",
    ),
    "CHAT_CONTEXT_LIMIT_REACHED": ErrorDefinition(
        code="CHAT_CONTEXT_LIMIT_REACHED",
        category="business",
        http_status=409,
        default_message="会话上下文已达到安全上限，请先手动压缩记忆",
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
    "SYSTEM_MODEL_CAPABILITY_MISSING": ErrorDefinition(
        code="SYSTEM_MODEL_CAPABILITY_MISSING",
        category="system",
        http_status=500,
        default_message="当前模型缺少上下文窗口配置",
    ),
    "SYSTEM_MCP_CONNECTION_FAILED": ErrorDefinition(
        code="SYSTEM_MCP_CONNECTION_FAILED",
        category="system",
        http_status=502,
        default_message="MCP Server 连接失败",
    ),
    "SYSTEM_ALERT_SOURCES_UNAVAILABLE": ErrorDefinition(
        code="SYSTEM_ALERT_SOURCES_UNAVAILABLE",
        category="system",
        http_status=503,
        default_message="活跃告警来源暂时不可用",
    ),
    "SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE": ErrorDefinition(
        code="SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE",
        category="system",
        http_status=503,
        default_message="当前没有可用的日志检索工具",
    ),
    "SYSTEM_UNAVAILABLE": ErrorDefinition(
        code="SYSTEM_UNAVAILABLE",
        category="system",
        http_status=503,
        default_message="运行时依赖暂时不可用",
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


AlertSourceType: TypeAlias = Literal["prometheus-v1", "alertmanager-v2"]
ActiveAlertStatus: TypeAlias = Literal["pending", "firing", "suppressed", "unprocessed"]


class AlertSource(ContractModel):
    name: str
    source_type: AlertSourceType = Field(alias="type")


class ActiveAlert(ContractModel):
    alert_name: str = Field(alias="alertName")
    service: str | None
    severity: str | None
    status: ActiveAlertStatus
    starts_at: str = Field(alias="startsAt")
    labels: dict[str, str]
    annotations: dict[str, str]
    source: AlertSource
    raw_context: dict[str, JsonValue] = Field(alias="rawContext")


class ActiveAlertsData(ContractModel):
    items: list[ActiveAlert]


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


McpTransport: TypeAlias = Literal["sse", "streamable_http"]
McpConnectionCheckStatus: TypeAlias = Literal["connected", "failed"]


class McpDiscoveredTool(ContractModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class McpConnection(ContractModel):
    id: str
    name: str
    transport: McpTransport
    url: str
    enabled: bool
    timeout_seconds: int = Field(alias="timeoutSeconds", ge=1, le=300)
    retries: int = Field(ge=0, le=5)
    last_check: str | None = Field(alias="lastCheck")
    last_error: str | None = Field(alias="lastError")
    discovered_tools: list[McpDiscoveredTool] = Field(alias="discoveredTools")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class McpConnectionListData(ContractModel):
    connections: list[McpConnection]


class CreateMcpConnectionRequest(ContractModel):
    name: str = Field(min_length=1, max_length=120)
    transport: McpTransport
    url: str = Field(min_length=1, max_length=4096)
    enabled: bool = True
    timeout_seconds: int = Field(default=30, alias="timeoutSeconds", ge=1, le=300)
    retries: int = Field(default=1, ge=0, le=5)

    @field_validator("name", "url")
    @classmethod
    def strip_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不得为空")
        return normalized

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MCP URL 必须是具有 host 的 HTTP/HTTPS URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("MCP URL 不允许包含 userinfo")
        return value


class UpdateMcpConnectionRequest(CreateMcpConnectionRequest):
    pass


class McpConnectionDeleteData(ContractModel):
    deleted: Literal[True] = True
    connection_id: str = Field(alias="connectionId")


class McpConnectionCheckResult(ContractModel):
    status: McpConnectionCheckStatus
    connection: McpConnection
    tools: list[McpDiscoveredTool]
    error: str | None = None


ChatMessageRole: TypeAlias = Literal["user", "assistant", "system", "tool"]


class ChatReference(ContractModel):
    chunk_id: str = Field(alias="chunkId", min_length=1)
    document_id: str = Field(alias="documentId", min_length=1)
    knowledge_base_id: str = Field(alias="knowledgeBaseId", min_length=1)
    source: str = Field(min_length=1)
    excerpt: str
    metadata: dict[str, JsonValue]
    vector_rank: int | None = Field(alias="vectorRank")
    vector_score: float | None = Field(alias="vectorScore")
    bm25_rank: int | None = Field(alias="bm25Rank")
    bm25_score: float | None = Field(alias="bm25Score")
    rrf_score: float = Field(alias="rrfScore")
    rerank_rank: int = Field(alias="rerankRank")
    rerank_score: float = Field(alias="rerankScore")
    score: float

    @model_validator(mode="after")
    def score_matches_rerank_score(self) -> "ChatReference":
        if self.score != self.rerank_score:
            raise ValueError("score 必须等于 rerankScore")
        return self


class ChatMessageMetadata(ContractModel):
    references: list[ChatReference] | None = None
    tool_call_ids: list[str] | None = Field(default=None, alias="toolCallIds")


class AppendChatMessageRequest(ContractModel):
    role: ChatMessageRole
    content: str = Field(min_length=1, max_length=100_000)
    metadata: ChatMessageMetadata = Field(default_factory=ChatMessageMetadata)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content 不得为空")
        return value


class ChatStreamMessageRequest(ContractModel):
    content: str = Field(min_length=1, max_length=100_000)
    metadata: ChatMessageMetadata = Field(default_factory=ChatMessageMetadata)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content 不得为空")
        return value


AgentToolCallAuditStatus: TypeAlias = Literal["started", "completed", "failed"]


class AgentToolCallAudit(ContractModel):
    id: str
    tool_call_id: str = Field(alias="toolCallId")
    chat_session_id: str | None = Field(alias="chatSessionId")
    diagnostic_task_id: str | None = Field(alias="diagnosticTaskId")
    tool_name: str = Field(alias="toolName")
    arguments: dict[str, JsonValue]
    status: AgentToolCallAuditStatus
    result_summary: str | None = Field(alias="resultSummary")
    error_message: str | None = Field(alias="errorMessage")
    started_at: str = Field(alias="startedAt")
    completed_at: str | None = Field(alias="completedAt")
    duration_ms: int | None = Field(alias="durationMs", ge=0)

    @model_validator(mode="after")
    def parent_must_be_exclusive(self) -> "AgentToolCallAudit":
        if (self.chat_session_id is None) == (self.diagnostic_task_id is None):
            raise ValueError("chatSessionId 与 diagnosticTaskId 必须恰好提供一个")
        return self


class AgentToolCallAuditListData(ContractModel):
    items: list[AgentToolCallAudit]


class ChatMessage(ContractModel):
    id: str
    session_id: str = Field(alias="sessionId")
    role: ChatMessageRole
    content: str
    sequence: int
    metadata: ChatMessageMetadata
    created_at: str = Field(alias="createdAt")


class ChatSession(ContractModel):
    id: str
    title: str
    memory_mode: ChatMemoryMode = Field(alias="memoryMode")
    memory_summary: str | None = Field(alias="memorySummary")
    context_tokens: int = Field(alias="contextTokens", ge=0)
    context_window_tokens: int = Field(alias="contextWindowTokens", gt=0)
    context_usage_percent: float = Field(alias="contextUsagePercent", ge=0)
    compacted_message_count: int = Field(alias="compactedMessageCount", ge=0)
    last_compacted_at: str | None = Field(alias="lastCompactedAt")
    can_compact: bool = Field(alias="canCompact")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ChatSessionListData(ContractModel):
    sessions: list[ChatSession]


class ChatSessionDetailData(ContractModel):
    session: ChatSession
    messages: list[ChatMessage]


class UpdateChatMemoryRequest(ContractModel):
    memory_mode: ChatMemoryMode = Field(alias="memoryMode")


class ChatDeleteData(ContractModel):
    deleted: Literal[True] = True
    session_id: str = Field(alias="sessionId")


class ChatPrompt(ContractModel):
    id: str
    label: str
    content: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ChatSkill(ContractModel):
    id: str
    name: str
    description: str
    filename: Literal["SKILL.md"] = "SKILL.md"
    content: str
    metadata: dict[str, JsonValue]
    summary: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ChatConfigurationData(ContractModel):
    prompts: list[ChatPrompt]
    skills: list[ChatSkill]
    selected_prompt_id: str | None = Field(alias="selectedPromptId")
    selected_skill_ids: list[str] = Field(alias="selectedSkillIds")


class UpdateChatConfigurationRequest(ContractModel):
    selected_prompt_id: str | None = Field(alias="selectedPromptId")
    selected_skill_ids: list[str] = Field(alias="selectedSkillIds", max_length=100)


class CreateChatPromptRequest(ContractModel):
    label: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("label", "content")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不得为空")
        return normalized


class UpdateChatPromptRequest(CreateChatPromptRequest):
    pass


class ChatAssetDeleteData(ContractModel):
    deleted: Literal[True] = True
    asset_id: str = Field(alias="assetId")


BackgroundJobStatus: TypeAlias = Literal["queued", "running", "succeeded", "failed", "cancelled"]
DocumentIndexStatus: TypeAlias = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class BackgroundJob(ContractModel):
    id: str
    owner_user_id: str = Field(alias="ownerUserId")
    kind: str
    resource_type: str | None = Field(default=None, alias="resourceType")
    resource_id: str | None = Field(default=None, alias="resourceId")
    status: BackgroundJobStatus
    payload: JsonValue
    attempt: int
    max_attempts: int = Field(alias="maxAttempts")
    timeout_seconds: int = Field(alias="timeoutSeconds")
    available_at: str = Field(alias="availableAt")
    lease_owner: str | None = Field(default=None, alias="leaseOwner")
    lease_expires_at: str | None = Field(default=None, alias="leaseExpiresAt")
    cancel_requested_at: str | None = Field(default=None, alias="cancelRequestedAt")
    retry_of_job_id: str | None = Field(default=None, alias="retryOfJobId")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    started_at: str | None = Field(default=None, alias="startedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")


class BackgroundJobEvent(ContractModel):
    sequence: int
    job_id: str = Field(alias="jobId")
    owner_user_id: str = Field(alias="ownerUserId")
    type: BackgroundJobStatus
    data: JsonValue
    created_at: str = Field(alias="createdAt")


class BackgroundJobListData(ContractModel):
    items: list[BackgroundJob]


DiagnosticStatus: TypeAlias = Literal["accepted", "running", "succeeded", "failed", "cancelled"]
DiagnosticStepStatus: TypeAlias = Literal["pending", "running", "succeeded", "failed", "cancelled"]
DiagnosticEvidenceKind: TypeAlias = Literal[
    "alert", "knowledge", "log", "log_hit", "log_context", "query_artifact", "metric"
]
DiagnosticReportGenerationMode: TypeAlias = Literal["model", "fallback"]
DiagnosticReportTrustState: TypeAlias = Literal[
    "verified_evidence", "insufficient_evidence", "execution_failed"
]
DiagnosticToolErrorCategory: TypeAlias = Literal[
    "input_validation",
    "output_validation",
    "empty_result",
    "timeout",
    "rate_limited",
    "transport",
    "provider_unavailable",
    "configuration",
    "permission",
    "owner_scope",
    "tool_not_allowed",
    "schema_incompatible",
    "permanent",
]


class DiagnosticPlanStep(ContractModel):
    position: int = Field(ge=0)
    tool_name: str = Field(alias="toolName", min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=500)
    arguments: dict[str, JsonValue]


class DiagnosticTask(ContractModel):
    id: str
    owner_user_id: str = Field(alias="ownerUserId")
    status: DiagnosticStatus
    query: str | None
    alerts: list[ActiveAlert]
    current_plan: list[DiagnosticPlanStep] = Field(alias="currentPlan")
    plan_version: int = Field(alias="planVersion", ge=0)
    replan_count: int = Field(alias="replanCount", ge=0)
    failure_code: str | None = Field(alias="failureCode")
    failure_reason: str | None = Field(alias="failureReason")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    started_at: str | None = Field(alias="startedAt")
    completed_at: str | None = Field(alias="completedAt")


class DiagnosticStep(ContractModel):
    id: str
    diagnostic_task_id: str = Field(alias="diagnosticTaskId")
    plan_version: int = Field(alias="planVersion", ge=1)
    position: int = Field(ge=0)
    attempt: int = Field(ge=1)
    tool_name: str = Field(alias="toolName")
    arguments: dict[str, JsonValue]
    status: DiagnosticStepStatus
    result_summary: str | None = Field(alias="resultSummary")
    error_message: str | None = Field(alias="errorMessage")
    error_category: DiagnosticToolErrorCategory | None = Field(alias="errorCategory")
    started_at: str | None = Field(alias="startedAt")
    completed_at: str | None = Field(alias="completedAt")
    created_at: str = Field(alias="createdAt")


class DiagnosticEvidence(ContractModel):
    id: str
    diagnostic_task_id: str = Field(alias="diagnosticTaskId")
    diagnostic_step_id: str | None = Field(alias="diagnosticStepId")
    tool_call_id: str | None = Field(alias="toolCallId")
    kind: DiagnosticEvidenceKind
    source: str
    title: str
    summary: str
    content: str
    metadata: dict[str, JsonValue]
    observed_at: str | None = Field(alias="observedAt")
    created_at: str = Field(alias="createdAt")


class DiagnosticEvidenceReference(ContractModel):
    evidence_id: str = Field(alias="evidenceId")
    kind: DiagnosticEvidenceKind
    source: str
    title: str
    excerpt: str
    metadata: dict[str, JsonValue]


class DiagnosticReport(ContractModel):
    id: str
    diagnostic_task_id: str = Field(alias="diagnosticTaskId")
    revision: int = Field(ge=1)
    markdown: str
    generation_mode: DiagnosticReportGenerationMode = Field(alias="generationMode")
    uncertainty: bool
    trust_state: DiagnosticReportTrustState = Field(alias="trustState")
    created_at: str = Field(alias="createdAt")


class ReportEvidenceLink(ContractModel):
    id: str
    diagnostic_task_id: str = Field(alias="diagnosticTaskId")
    report_id: str = Field(alias="reportId")
    evidence_id: str = Field(alias="evidenceId")
    claim_key: str = Field(alias="claimKey")
    section: str
    position: int = Field(ge=0)


def _empty_active_alerts() -> list[ActiveAlert]:
    return []


class CreateDiagnosticRequest(ContractModel):
    alerts: list[ActiveAlert] = Field(default_factory=_empty_active_alerts, max_length=20)
    query: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_query_or_alert(self) -> "CreateDiagnosticRequest":
        if self.query is not None:
            self.query = self.query.strip() or None
        if self.query is None and not self.alerts:
            raise ValueError("query 与 alerts 至少提供一项")
        return self


class DiagnosticStreamRequest(ContractModel):
    after_sequence: int = Field(default=0, alias="afterSequence", ge=0)


class DiagnosticCreateData(ContractModel):
    task: DiagnosticTask
    background_job: BackgroundJob = Field(alias="backgroundJob")


class DiagnosticListData(ContractModel):
    items: list[DiagnosticTask]


class DiagnosticDetailData(ContractModel):
    task: DiagnosticTask
    background_job: BackgroundJob = Field(alias="backgroundJob")
    steps: list[DiagnosticStep]
    report: DiagnosticReport | None


class DiagnosticEvidenceChainData(ContractModel):
    task_id: str = Field(alias="taskId")
    evidence: list[DiagnosticEvidence]
    report_evidence_links: list[ReportEvidenceLink] = Field(alias="reportEvidenceLinks")
    tool_audits: list[AgentToolCallAudit] = Field(alias="toolAudits")


class DiagnosticCase(ContractModel):
    id: str
    owner_user_id: str = Field(alias="ownerUserId")
    task_id: str = Field(alias="taskId")
    report_id: str = Field(alias="reportId")
    document_id: str = Field(alias="documentId")
    index_task_id: str = Field(alias="indexTaskId")
    alert_name: str = Field(alias="alertName")
    service: str
    keywords: list[str]
    root_cause: str = Field(alias="rootCause")
    remediation: str
    summary: str
    evidence_ids: list[str] = Field(alias="evidenceIds")
    incident_fingerprint: str | None = Field(alias="incidentFingerprint")
    knowledge_fingerprint: str | None = Field(alias="knowledgeFingerprint")
    fingerprint_version: str | None = Field(alias="fingerprintVersion")
    promotion_status: Literal["legacy", "canonical"] = Field(alias="promotionStatus")
    created_at: str = Field(alias="createdAt")


class DiagnosticCasePromotionCandidate(ContractModel):
    item: DiagnosticCase
    similarity_score: float = Field(alias="similarityScore", ge=0, le=1)


class PromoteDiagnosticCaseRequest(ContractModel):
    resolution: Literal["create_new", "merge"] | None = None
    candidate_case_id: str | None = Field(
        default=None, alias="candidateCaseId", min_length=1, max_length=32
    )

    @model_validator(mode="after")
    def validate_resolution_candidate(self) -> "PromoteDiagnosticCaseRequest":
        if self.resolution == "merge" and self.candidate_case_id is None:
            raise ValueError("merge 必须提供 candidateCaseId")
        if self.resolution != "merge" and self.candidate_case_id is not None:
            raise ValueError("只有 merge 可提供 candidateCaseId")
        return self


class DiagnosticCasePromotionResult(ContractModel):
    status: Literal["created", "existing", "needs_review", "merged"]
    item: DiagnosticCase | None
    candidates: list[DiagnosticCasePromotionCandidate]


class DiagnosticCaseListData(ContractModel):
    items: list[DiagnosticCase]


class DiagnosticCaseDetailData(ContractModel):
    item: DiagnosticCase


FeedbackTargetType: TypeAlias = Literal[
    "chat_message", "citation", "diagnostic_step", "diagnostic_report"
]
FeedbackRating: TypeAlias = Literal["positive", "negative"]
FeedbackReason: TypeAlias = Literal[
    "incorrect", "incomplete", "irrelevant", "unclear", "unsafe", "other"
]


class UserFeedback(ContractModel):
    id: str
    target_type: FeedbackTargetType = Field(alias="targetType")
    target_id: str = Field(alias="targetId")
    subject_id: str | None = Field(alias="subjectId")
    rating: FeedbackRating
    reason: FeedbackReason | None
    comment: str | None
    correction: str | None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class FeedbackListData(ContractModel):
    items: list[UserFeedback]


class UserFeedbackUpsertRequest(ContractModel):
    target_type: FeedbackTargetType = Field(alias="targetType")
    target_id: str = Field(alias="targetId", min_length=1, max_length=128)
    subject_id: str | None = Field(default=None, alias="subjectId", max_length=128)
    rating: FeedbackRating
    reason: FeedbackReason | None = None
    comment: str | None = Field(default=None, max_length=2000)
    correction: str | None = Field(default=None, max_length=4000)

    @field_validator(
        "target_id", "subject_id", "reason", "comment", "correction", mode="before"
    )
    @classmethod
    def trim_feedback_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_subject_shape(self) -> "UserFeedbackUpsertRequest":
        subject = self.subject_id.strip() if self.subject_id is not None else ""
        if self.target_type == "citation" and not subject:
            raise ValueError("citation 必须提供 subjectId")
        if self.target_type != "citation" and subject:
            raise ValueError(f"{self.target_type} 不接受 subjectId")
        return self


class FeedbackDeleteData(ContractModel):
    deleted: Literal[True] = True
    feedback_id: str = Field(alias="feedbackId")


class DocumentIndexTaskModel(ContractModel):
    id: str
    knowledge_base_id: str = Field(alias="knowledgeBaseId")
    document_id: str = Field(alias="documentId")
    status: DocumentIndexStatus
    failure_reason: str | None = Field(default=None, alias="failureReason")
    retry_of_task_id: str | None = Field(default=None, alias="retryOfTaskId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    started_at: str | None = Field(default=None, alias="startedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")


class KnowledgeBaseModel(ContractModel):
    id: str
    name: str = "默认知识库"
    is_default: Literal[True] = Field(default=True, alias="isDefault")


class KnowledgeBaseListData(ContractModel):
    items: list[KnowledgeBaseModel]


class ChunkingConfigModel(ContractModel):
    strategy: Literal["fixed-character", "markdown-heading", "paragraph"]
    max_characters: int | None = Field(default=None, alias="maxCharacters")
    overlap: int | None = None


class KnowledgeDocumentModel(ContractModel):
    id: str
    knowledge_base_id: str = Field(alias="knowledgeBaseId")
    filename: str
    size_bytes: int = Field(alias="sizeBytes")
    mime_type: Literal["text/markdown", "application/pdf"] = Field(alias="mimeType")
    sha256: str
    uploaded_at: str = Field(alias="uploadedAt")
    index_status: DocumentIndexStatus = Field(alias="indexStatus")
    chunking_config: ChunkingConfigModel = Field(alias="chunkingConfig")


class SaveDiagnosisToKnowledgeData(ContractModel):
    document: KnowledgeDocumentModel
    index_task: DocumentIndexTaskModel = Field(alias="indexTask")


class KnowledgeDocumentListData(ContractModel):
    items: list[KnowledgeDocumentModel]


class ChunkPreviewItemModel(ContractModel):
    index: int
    excerpt: str
    metadata: dict[str, JsonValue]


class ChunkPreviewData(ContractModel):
    total_chunks: int = Field(alias="totalChunks")
    items: list[ChunkPreviewItemModel]


class KnowledgeRetrievalToolInput(ContractModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", frozen=True)

    query: str = Field(min_length=1, max_length=10_000)
    topK: int = Field(default=5, ge=1, le=5)
    knowledgeBaseIds: tuple[str, ...] | None = None
    documentIds: tuple[str, ...] | None = None

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @property
    def top_k(self) -> int:
        return self.topK

    @property
    def knowledge_base_ids(self) -> tuple[str, ...] | None:
        return self.knowledgeBaseIds

    @property
    def document_ids(self) -> tuple[str, ...] | None:
        return self.documentIds


class KnowledgeRetrievalCitation(ContractModel):
    chunk_id: str = Field(alias="chunkId")
    document_id: str = Field(alias="documentId")
    knowledge_base_id: str = Field(alias="knowledgeBaseId")
    source: str
    excerpt: str
    metadata: dict[str, JsonValue]
    vector_rank: int | None = Field(alias="vectorRank")
    vector_score: float | None = Field(alias="vectorScore")
    bm25_rank: int | None = Field(alias="bm25Rank")
    bm25_score: float | None = Field(alias="bm25Score")
    rrf_score: float = Field(alias="rrfScore")
    rerank_rank: int = Field(alias="rerankRank")
    rerank_score: float = Field(alias="rerankScore")
    score: float

    @model_validator(mode="after")
    def score_matches_rerank_score(self) -> "KnowledgeRetrievalCitation":
        if self.score != self.rerank_score:
            raise ValueError("score 必须等于 rerankScore")
        return self


class KnowledgeRetrievalToolOutput(ContractModel):
    results: list[KnowledgeRetrievalCitation]


class SseEventBase(ContractModel):
    id: str
    sequence: int = Field(ge=1)
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


class ReferenceSource(ChatReference):
    """SSE 引用与持久 Chat 引用完全同形。"""


class ReferenceSourceData(ContractModel):
    source: ReferenceSource


class ReferenceSourceEvent(SseEventBase):
    type: Literal["reference.source"] = "reference.source"
    data: ReferenceSourceData


class DiagnosticReferenceSourceData(ContractModel):
    source: DiagnosticEvidenceReference


class DiagnosticReferenceSourceEvent(SseEventBase):
    type: Literal["reference.source"] = "reference.source"
    data: DiagnosticReferenceSourceData


class TaskStatusData(ContractModel):
    task_id: str = Field(alias="taskId")
    status: TaskLifecycle
    message: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)


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
