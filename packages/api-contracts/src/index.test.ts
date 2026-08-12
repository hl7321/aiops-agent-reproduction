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

  it("所有受保护 path 复用统一 bearer、401 与 403 policy", () => {
    expect(PROTECTED_PATH_POLICY).toEqual({
      security: "BearerAuth",
      errors: ["AUTH_REQUIRED", "AUTH_FORBIDDEN"],
    });
    expect(PROTECTED_PATH_POLICY).toEqual(manifest.openapi.protectedPathPolicy);

    for (const [path, definition] of Object.entries(OPENAPI_PATHS)) {
      if (definition.security?.includes("BearerAuth")) {
        expect(definition.errors, path).toEqual(PROTECTED_PATH_POLICY.errors);
      }
    }
    expect(ERROR_DEFINITIONS.BUSINESS_RESOURCE_NOT_FOUND).toEqual({
      code: "BUSINESS_RESOURCE_NOT_FOUND",
      category: "business",
      httpStatus: 404,
      defaultMessage: "请求的资源不存在",
    });
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
