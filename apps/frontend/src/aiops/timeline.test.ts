import { describe, expect, it } from "vitest";

import type { SseEvent } from "@super-ai/api-contracts";

import type { DiagnosticDetailData } from "@super-ai/api-contracts";

import { buildLiveTimeline, buildPersistentExecutionChain } from "./timeline";

describe("AIOps timeline", () => {
  it("把共享事件映射为 phase，而不创造新状态或泄漏 raw JSON", () => {
    const events: SseEvent[] = [
      { id: "1", sequence: 1, type: "task.status", channel: "aiops", timestamp: "now",
        data: { taskId: "t", status: "running", message: "Replanner 正在调整计划" } },
      { id: "2", sequence: 2, type: "tool.call", channel: "aiops", timestamp: "now",
        data: { toolCallId: "c", toolName: "SearchLog", lifecycle: "completed",
          output: { secret: "raw-output-must-not-render" } } },
      { id: "3", sequence: 3, type: "report", channel: "aiops", timestamp: "now",
        data: { report: { markdown: "raw-report-payload" } } },
      { id: "4", sequence: 4, type: "tool.call", channel: "aiops", timestamp: "now",
        data: { toolCallId: "failed", toolName: "SearchLog", lifecycle: "failed",
          input: { query: "private-query" }, error: { code: "SYSTEM_INTERNAL_ERROR",
            category: "system", httpStatus: 500, message: "工具调用失败" } } },
      { id: "5", sequence: 5, type: "error", channel: "aiops", timestamp: "now",
        data: { error: { code: "SYSTEM_INTERNAL_ERROR", category: "system", httpStatus: 500,
          message: "模型不可用" } } },
    ];
    const timeline = buildLiveTimeline(events);

    expect(timeline.map((entry) => entry.phase)).toEqual([
      "replanner", "executor", "report", "executor", "task",
    ]);
    expect(timeline.map((entry) => entry.status)).toEqual([
      "running", "succeeded", "succeeded", "failed", "failed",
    ]);
    expect(JSON.stringify(timeline)).not.toContain("raw-output-must-not-render");
    expect(JSON.stringify(timeline)).not.toContain("raw-report-payload");
    expect(JSON.stringify(timeline)).not.toContain("private-query");
    expect(timeline[1]?.detail).toContain("原始参数与工具输出不会在页面显示");
  });

  it("持久执行链显示 attempt 与安全错误分类，不显示参数值", () => {
    const detail = {
      task: { id: "task", ownerUserId: "owner", status: "failed", query: null, alerts: [],
        currentPlan: [], planVersion: 1, replanCount: 0, failureCode: "SYSTEM_UNAVAILABLE",
        failureReason: "schema invalid", createdAt: "now", updatedAt: "now", startedAt: "now",
        completedAt: "now" },
      backgroundJob: { id: "job", ownerUserId: "owner", kind: "aiops_diagnosis",
        resourceType: "diagnostic_task", resourceId: "task", status: "failed", payload: {},
        attempt: 1, maxAttempts: 3, timeoutSeconds: 600, availableAt: "now", createdAt: "now",
        updatedAt: "now" },
      steps: [{ id: "step", diagnosticTaskId: "task", planVersion: 1, position: 0, attempt: 2,
        toolName: "DescribeLogContext", arguments: { PkgId: "private-value" }, status: "failed",
        resultSummary: null, errorMessage: "响应结构不兼容", errorCategory: "output_validation",
        startedAt: "now", completedAt: "now", createdAt: "now" }], report: null,
    } satisfies DiagnosticDetailData;

    const chain = buildPersistentExecutionChain(detail, null);
    expect(chain[0]?.summary).toContain("第 2 次尝试");
    expect(chain[0]?.summary).toContain("output_validation");
    expect(JSON.stringify(chain)).not.toContain("private-value");
  });
});
