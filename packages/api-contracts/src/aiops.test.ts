import { describe, expect, expectTypeOf, it } from "vitest";

import manifest from "../contract-manifest.json";
import type {
  DiagnosticCreateData,
  DiagnosticEvidenceChainData,
  DiagnosticTask,
  TaskStatusEvent,
} from "./index";
import { AIOPS_DIAGNOSTIC_OPERATIONS, ERROR_DEFINITIONS, isSseEvent } from "./index";

describe("AIOps 诊断共享合同", () => {
  it("定义任务、创建结果和证据链", () => {
    expectTypeOf<DiagnosticTask>().toHaveProperty("status");
    expectTypeOf<DiagnosticCreateData>().toHaveProperty("backgroundJob");
    expectTypeOf<DiagnosticEvidenceChainData>().toHaveProperty("reportEvidenceLinks");
  });

  it("登记五个受保护 path 且没有专用 cancel/retry", () => {
    expect(AIOPS_DIAGNOSTIC_OPERATIONS).toEqual(manifest.openapi.aiopsDiagnosticOperations);
    expect(AIOPS_DIAGNOSTIC_OPERATIONS).toHaveLength(5);
    expect(AIOPS_DIAGNOSTIC_OPERATIONS.every((item) =>
      item.security.includes("BearerAuth")
      && item.errors.includes("AUTH_REQUIRED")
      && item.errors.includes("AUTH_FORBIDDEN"))).toBe(true);
    expect(AIOPS_DIAGNOSTIC_OPERATIONS.some((item) => /cancel|retry/.test(item.path))).toBe(false);
  });

  it("定义 SearchLog 缺失错误和有界任务进度", () => {
    expect(ERROR_DEFINITIONS.SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE).toEqual({
      code: "SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE",
      category: "system",
      httpStatus: 503,
      defaultMessage: "当前没有可用的日志检索工具",
    });
    const event: TaskStatusEvent = {
      id: "event-1",
      sequence: 1,
      type: "task.status",
      channel: "aiops",
      timestamp: "2026-08-20T00:00:00Z",
      data: { taskId: "task-1", status: "cancelled", message: "已取消", progress: 50 },
    };
    expect(event.data.progress).toBe(50);
    expect(isSseEvent(event)).toBe(true);
    expect(isSseEvent({ ...event, data: { ...event.data, status: "completed" } })).toBe(false);
    expect(isSseEvent({ ...event, data: { ...event.data, progress: 101 } })).toBe(false);
  });
});
