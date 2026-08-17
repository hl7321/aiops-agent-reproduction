import { describe, expect, expectTypeOf, it } from "vitest";

import manifest from "../contract-manifest.json";
import {
  ERROR_DEFINITIONS,
  OPENAPI_PATHS,
  OPENAPI_SECURITY_SCHEMES,
  PROTECTED_PATH_POLICY,
  SSE_EVENT_TYPES,
  TOOL_CALL_LIFECYCLES,
  isApiEnvelope,
  KNOWLEDGE_OPENAPI_OPERATIONS,
  KNOWLEDGE_UPLOAD_POLICY,
  DOCUMENT_INDEX_OPENAPI_OPERATIONS,
} from "./index";
import type {
  ApiError,
  AuthUser,
  ErrorEvent,
  FailureEnvelope,
  FoundationStatus,
  LoginData,
  LoginRequest,
  LogoutData,
  RegisterRequest,
  SuccessEnvelope,
  ToolCallEvent,
  BackgroundJob,
  BackgroundJobEvent,
  DocumentIndexTask,
  DocumentIndexStatus,
  KnowledgeRetrievalCitation,
  KnowledgeRetrievalToolInput,
  KnowledgeRetrievalToolOutput,
} from "./index";

describe("HTTP 合同", () => {
  it("表达成功、业务失败、验证失败和系统失败四类 envelope", () => {
    const success: SuccessEnvelope<FoundationStatus> = {
      ok: true,
      data: { status: "ok" },
      meta: { requestId: "req-success" },
    };
    const businessFailure: FailureEnvelope = {
      ok: false,
      error: {
        code: "BUSINESS_RULE_VIOLATION",
        category: "business",
        httpStatus: 409,
        message: "请求与当前业务规则冲突",
      },
      meta: { requestId: "req-business" },
    };
    const validationFailure: FailureEnvelope = {
      ok: false,
      error: {
        code: "VALIDATION_REQUEST_INVALID",
        category: "validation",
        httpStatus: 422,
        message: "请求参数验证失败",
        details: { fields: [{ path: "query.limit", type: "int_parsing" }] },
      },
      meta: { requestId: "req-validation" },
    };
    const systemFailure: FailureEnvelope = {
      ok: false,
      error: {
        code: "SYSTEM_INTERNAL_ERROR",
        category: "system",
        httpStatus: 500,
        message: "服务暂时不可用",
      },
      meta: { requestId: "req-system" },
    };

    expect(success).toEqual({
      ok: true,
      data: { status: "ok" },
      meta: { requestId: "req-success" },
    });
    expect([businessFailure, validationFailure, systemFailure].map((item) => item.error.code))
      .toEqual([
        "BUSINESS_RULE_VIOLATION",
        "VALIDATION_REQUEST_INVALID",
        "SYSTEM_INTERNAL_ERROR",
      ]);
  });

  it("公开稳定错误目录并与机器可读 manifest 对齐", () => {
    expect(ERROR_DEFINITIONS).toEqual(manifest.errors);
    expect(Object.keys(ERROR_DEFINITIONS)).toEqual([
      "AUTH_REQUIRED",
      "AUTH_FORBIDDEN",
      "AUTH_INVALID_CREDENTIALS",
      "AUTH_EMAIL_ALREADY_REGISTERED",
      "BUSINESS_RULE_VIOLATION",
      "BUSINESS_CONFLICT",
      "BUSINESS_RESOURCE_NOT_FOUND",
      "VALIDATION_REQUEST_INVALID",
      "SYSTEM_ROUTE_NOT_FOUND",
      "SYSTEM_METHOD_NOT_ALLOWED",
      "SYSTEM_INTERNAL_ERROR",
    ]);
    expect(ERROR_DEFINITIONS.AUTH_REQUIRED).toEqual({
      code: "AUTH_REQUIRED",
      category: "authentication",
      httpStatus: 401,
      defaultMessage: "需要认证后才能访问",
    });
  });

  it("公开认证错误、Auth DTO 与 bearer OpenAPI 合同", () => {
    const register: RegisterRequest = { email: "USER@example.com", password: "secret-123" };
    const login: LoginRequest = register;
    const user: AuthUser = {
      id: "user-1",
      email: "user@example.com",
      createdAt: "2026-08-08T00:00:00Z",
    };
    const loginData: LoginData = { user, token: "raw-token" };
    const logoutData: LogoutData = { revoked: true };

    expect({ register, login, loginData, logoutData }).toMatchObject({
      loginData: { user, token: "raw-token" },
      logoutData: { revoked: true },
    });
    expect(ERROR_DEFINITIONS.AUTH_INVALID_CREDENTIALS).toEqual({
      code: "AUTH_INVALID_CREDENTIALS",
      category: "authentication",
      httpStatus: 401,
      defaultMessage: "邮箱或密码错误",
    });
    expect(OPENAPI_SECURITY_SCHEMES).toEqual(manifest.openapi.securitySchemes);
    expect(OPENAPI_SECURITY_SCHEMES.BearerAuth).toEqual({ type: "http", scheme: "bearer" });
  });

  it("登记 foundation health 的机器可读 OpenAPI path", () => {
    expect(OPENAPI_PATHS).toEqual(manifest.openapi.paths);
    expect(OPENAPI_PATHS["/health"]).toEqual({
      method: "GET",
      operationId: "getHealth",
      successData: "FoundationStatus",
    });
  });

  it("登记四个认证 path 并仅保护 logout 与 me", () => {
    expect(Object.keys(OPENAPI_PATHS)).toEqual([
      "/health",
      "/auth/register",
      "/auth/login",
      "/auth/logout",
      "/auth/me",
      "/chat/sessions",
      "/chat/sessions/{id}",
      "/chat/sessions/{id}/messages",
      "/chat/sessions/{id}/messages:clear",
      "/background-jobs",
      "/background-jobs/{id}",
      "/background-jobs/{id}:cancel",
      "/background-jobs/{id}:retry",
      "/knowledge-bases",
      "/knowledge-bases/{kb}/documents",
      "/knowledge-bases/{kb}/documents/{document}",
      "/knowledge-bases/{kb}/documents/{document}/chunk-preview",
      "/knowledge-bases/{kb}/documents/{document}/index-tasks",
      "/knowledge-bases/{kb}/documents/{document}/index-tasks/{task}",
      "/knowledge-bases/{kb}/documents/{document}/index-tasks/{task}:retry",
    ]);
    expect(OPENAPI_PATHS["/auth/register"]).toEqual({
      method: "POST",
      operationId: "registerUser",
      successData: "AuthUser",
    });
    expect(OPENAPI_PATHS["/auth/login"]).toEqual({
      method: "POST",
      operationId: "loginUser",
      successData: "LoginData",
    });
    expect(OPENAPI_PATHS["/auth/logout"]).toEqual({
      method: "POST",
      operationId: "logoutUser",
      successData: "LogoutData",
      security: ["BearerAuth"],
      errors: ["AUTH_REQUIRED", "AUTH_FORBIDDEN"],
    });
    expect(OPENAPI_PATHS["/auth/me"]).toEqual({
      method: "GET",
      operationId: "getCurrentUser",
      successData: "AuthUser",
      security: ["BearerAuth"],
      errors: ["AUTH_REQUIRED", "AUTH_FORBIDDEN"],
    });
  });

  it("登记知识文档上传 policy 与六种 OpenAPI 操作", () => {
    expect(KNOWLEDGE_UPLOAD_POLICY).toEqual({
      maxBytes: 10 * 1024 * 1024,
      allowedTypes: { ".md": "text/markdown", ".pdf": "application/pdf" },
      multipart: { file: "file", chunkingConfig: "chunkingConfig", overwrite: "overwrite" },
      strategies: ["fixed-character", "markdown-heading", "paragraph"],
    });
    expect(KNOWLEDGE_OPENAPI_OPERATIONS.map((item) => item.operationId)).toEqual([
      "listKnowledgeBases", "listKnowledgeDocuments", "uploadKnowledgeDocument",
      "getKnowledgeDocument", "deleteKnowledgeDocument", "previewKnowledgeDocumentChunks",
    ]);
    for (const operation of KNOWLEDGE_OPENAPI_OPERATIONS) {
      expect(operation.security).toEqual(["BearerAuth"]);
      expect(operation.errors).toEqual(expect.arrayContaining(["AUTH_REQUIRED", "AUTH_FORBIDDEN"]));
      expect(operation.successData.length).toBeGreaterThan(0);
    }
  });

  it("登记无 jobId 的 durable 文档索引任务与三种操作", () => {
    const statuses: readonly DocumentIndexStatus[] = [
      "pending", "running", "succeeded", "failed", "cancelled",
    ];
    const task: DocumentIndexTask = {
      id: "task-1", knowledgeBaseId: "kb-1", documentId: "doc-1", status: "failed",
      failureReason: "provider unavailable", retryOfTaskId: null,
      createdAt: "2026-08-13T00:00:00Z", updatedAt: "2026-08-13T00:01:00Z",
      startedAt: "2026-08-13T00:00:10Z", completedAt: "2026-08-13T00:01:00Z",
    };
    expect(statuses).toEqual(["pending", "running", "succeeded", "failed", "cancelled"]);
    expect(task).not.toHaveProperty("jobId");
    expect(DOCUMENT_INDEX_OPENAPI_OPERATIONS.map((item) => item.operationId)).toEqual([
      "createDocumentIndexTask", "getDocumentIndexTask", "retryDocumentIndexTask",
    ]);
    expect(DOCUMENT_INDEX_OPENAPI_OPERATIONS.every((item) =>
      item.security.includes("BearerAuth") && item.successData === "DocumentIndexTask"
    )).toBe(true);
  });

  it("登记不暴露 owner/tenant 或 HTTP path 的 knowledge retrieval Tool 合同", () => {
    const input: KnowledgeRetrievalToolInput = {
      query: "订单服务 trace_id",
      topK: 3,
      knowledgeBaseIds: ["kb-1"],
      documentIds: ["doc-1"],
    };
    const citation: KnowledgeRetrievalCitation = {
      chunkId: "chunk-1",
      documentId: "doc-1",
      knowledgeBaseId: "kb-1",
      source: "runbook.md",
      excerpt: "trace_id 对应订单服务异常",
      metadata: { strategy: "paragraph", index: 0 },
      vectorRank: 1,
      vectorScore: 0.9,
      bm25Rank: null,
      bm25Score: null,
      rrfScore: 1 / 61,
      rerankRank: 1,
      rerankScore: 0.12,
      score: 0.12,
    };
    const output: KnowledgeRetrievalToolOutput = { results: [citation] };

    expect(input).not.toHaveProperty("ownerUserId");
    expect(input).not.toHaveProperty("tenantId");
    expect(output.results[0]?.score).toBe(output.results[0]?.rerankScore);
    expect(Object.keys(OPENAPI_PATHS).some((path) => path.includes("search"))).toBe(false);
  });

  it("所有受保护 path 复用统一 bearer、401 与 403 policy", () => {
    expect(PROTECTED_PATH_POLICY).toEqual({
      security: "BearerAuth",
      errors: ["AUTH_REQUIRED", "AUTH_FORBIDDEN"],
    });
    expect(PROTECTED_PATH_POLICY).toEqual(manifest.openapi.protectedPathPolicy);

    for (const [path, definition] of Object.entries(OPENAPI_PATHS)) {
      if (definition.security?.includes("BearerAuth")) {
        expect(definition.errors, path).toEqual(
          expect.arrayContaining([...PROTECTED_PATH_POLICY.errors]),
        );
      }
    }
    expect(ERROR_DEFINITIONS.BUSINESS_RESOURCE_NOT_FOUND).toEqual({
      code: "BUSINESS_RESOURCE_NOT_FOUND",
      category: "business",
      httpStatus: 404,
      defaultMessage: "请求的资源不存在",
    });
  });

  it("登记持久后台任务 DTO 与四个受保护 path", () => {
    const job: BackgroundJob = {
      id: "job-1", ownerUserId: "user-1", kind: "index.document", status: "queued",
      payload: { documentId: "doc-1" }, attempt: 0, maxAttempts: 3, timeoutSeconds: 300,
      availableAt: "2026-08-12T00:00:00Z", createdAt: "2026-08-12T00:00:00Z",
      updatedAt: "2026-08-12T00:00:00Z",
    };
    const event: BackgroundJobEvent = {
      sequence: 1, jobId: job.id, ownerUserId: job.ownerUserId, type: "queued",
      data: {}, createdAt: "2026-08-12T00:00:00Z",
    };
    expect(event.type).toBe(job.status);
    for (const path of [
      "/background-jobs", "/background-jobs/{id}",
      "/background-jobs/{id}:cancel", "/background-jobs/{id}:retry",
    ] as const) {
      expect(OPENAPI_PATHS[path].security).toEqual(["BearerAuth"]);
      expect(OPENAPI_PATHS[path].errors).toEqual(expect.arrayContaining(["AUTH_REQUIRED", "AUTH_FORBIDDEN"]));
    }
    expect(job).not.toHaveProperty("heartbeatAt");
    expect(job).not.toHaveProperty("result");
  });

  it("拒绝 code 或元数据偏离稳定目录的失败 envelope", () => {
    expect(isApiEnvelope({
      ok: false,
      error: {
        code: "TEMPORARY_ERROR",
        category: "system",
        httpStatus: 500,
        message: "temporary",
      },
      meta: { requestId: "req-temp" },
    })).toBe(false);
    expect(isApiEnvelope({
      ok: false,
      error: {
        code: "AUTH_REQUIRED",
        category: "business",
        httpStatus: 409,
        message: "wrong metadata",
      },
      meta: { requestId: "req-mismatch" },
    })).toBe(false);
  });
});

describe("SSE 合同", () => {
  it("公开完整事件目录和工具生命周期", () => {
    expect(SSE_EVENT_TYPES).toEqual([
      "content.delta",
      "reasoning.delta",
      "tool.call",
      "reference.source",
      "task.status",
      "report",
      "complete",
      "error",
    ]);
    expect(TOOL_CALL_LIFECYCLES).toEqual(["started", "delta", "completed", "failed"]);
    expect(SSE_EVENT_TYPES).toEqual(manifest.sse.eventTypes);
    expect(TOOL_CALL_LIFECYCLES).toEqual(manifest.sse.toolCallLifecycles);
  });

  it("tool.call 支持稳定 lifecycle 和公共字段", () => {
    const event: ToolCallEvent = {
      id: "evt-tool",
      type: "tool.call",
      channel: "aiops",
      timestamp: "2026-08-07T12:00:00Z",
      data: {
        toolCallId: "call-1",
        toolName: "query_alerts",
        lifecycle: "started",
      },
    };

    expect(event.data.lifecycle).toBe("started");
    expect(event.channel).toBe("aiops");
  });

  it("error 事件直接复用 HTTP ApiError", () => {
    const error: ApiError = {
      code: "SYSTEM_INTERNAL_ERROR",
      category: "system",
      httpStatus: 500,
      message: "服务暂时不可用",
    };
    const event: ErrorEvent = {
      id: "evt-error",
      type: "error",
      channel: "chat",
      timestamp: "2026-08-07T12:00:01Z",
      data: { error },
    };

    expect(event.data.error).toBe(error);
    expectTypeOf(event.data.error).toEqualTypeOf<ApiError>();
  });
});
