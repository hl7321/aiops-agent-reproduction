import { describe, expect, expectTypeOf, it } from "vitest";

import manifest from "../contract-manifest.json";
import type {
  DiagnosticCase,
  DiagnosticCasePromotionResult,
  DiagnosticCreateData,
  DiagnosticEvidenceChainData,
  DiagnosticReport,
  DiagnosticStep,
  DiagnosticToolErrorCategory,
  DiagnosticTask,
  PromoteDiagnosticCaseRequest,
  TaskStatusEvent,
} from "./index";
import {
  AIOPS_CASE_OPERATIONS,
  AIOPS_DIAGNOSTIC_OPERATIONS,
  ERROR_DEFINITIONS,
  isSseEvent,
} from "./index";

describe("AIOps 诊断共享合同", () => {
  it("定义任务、创建结果和证据链", () => {
    expectTypeOf<DiagnosticTask>().toHaveProperty("status");
    expectTypeOf<DiagnosticCreateData>().toHaveProperty("backgroundJob");
    expectTypeOf<DiagnosticEvidenceChainData>().toHaveProperty("reportEvidenceLinks");
  });

  it("公开 step attempt/错误分类和 report 可信状态", () => {
    expectTypeOf<DiagnosticStep["attempt"]>().toEqualTypeOf<number>();
    expectTypeOf<DiagnosticStep["errorCategory"]>()
      .toEqualTypeOf<DiagnosticToolErrorCategory | null>();
    expectTypeOf<DiagnosticReport["trustState"]>()
      .toEqualTypeOf<"verified_evidence" | "insufficient_evidence" | "execution_failed">();
  });

  it("定义显式提升、精确重复和语义相似候选合同", () => {
    expectTypeOf<PromoteDiagnosticCaseRequest["resolution"]>()
      .toEqualTypeOf<"create_new" | "merge" | undefined>();
    expectTypeOf<DiagnosticCasePromotionResult["status"]>()
      .toEqualTypeOf<"created" | "existing" | "needs_review" | "merged">();
    expectTypeOf<DiagnosticCasePromotionResult>().toHaveProperty("candidates");
  });

  it("定义诊断 case 与四条受保护操作", () => {
    expectTypeOf<DiagnosticCase>().toHaveProperty("indexTaskId");
    expect(AIOPS_CASE_OPERATIONS).toEqual(manifest.openapi.aiopsCaseOperations);
    expect(AIOPS_CASE_OPERATIONS).toHaveLength(4);
    expect(AIOPS_CASE_OPERATIONS.every((item) => item.security.includes("BearerAuth"))).toBe(true);
    expect(AIOPS_CASE_OPERATIONS[2]?.errors).toContain("VALIDATION_REQUEST_INVALID");
    expect(AIOPS_CASE_OPERATIONS[3]).toMatchObject({
      path: "/aiops/diagnostics/{id}:promote-to-knowledge",
      method: "POST",
      operationId: "promoteAiopsDiagnosticCase",
      successData: "DiagnosticCasePromotionResult",
    });
    expect(AIOPS_CASE_OPERATIONS[3]?.errors).toContain("BUSINESS_RULE_VIOLATION");
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
