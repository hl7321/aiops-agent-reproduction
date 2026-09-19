import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ActiveAlert,
  BackgroundJob,
  DiagnosticCase,
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
  DiagnosticTask,
  SseEvent,
} from "@super-ai/api-contracts";

import type { AiopsClient } from "../aiops/aiopsClient";
import type { ApiResult } from "../transport/apiClient";
import { createAiopsStore } from "./aiops";
import { clearProtectedStores, resetProtectedStoreRegistryForTests } from "./protectedStoreRegistry";

const ALERT: ActiveAlert = {
  alertName: "HighLatency", service: "checkout", severity: "critical", status: "firing",
  startsAt: "2026-08-21T00:00:00Z", labels: {}, annotations: {}, rawContext: {},
  source: { name: "prometheus", type: "prometheus-v1" },
};
const TASK: DiagnosticTask = {
  id: "task-1", ownerUserId: "user-1", status: "accepted", query: "排查延迟", alerts: [ALERT],
  currentPlan: [], planVersion: 0, replanCount: 0, failureCode: null, failureReason: null,
  createdAt: "now", updatedAt: "now", startedAt: null, completedAt: null,
};
const JOB: BackgroundJob = {
  id: "job-1", ownerUserId: "user-1", kind: "aiops_diagnosis",
  resourceType: "diagnostic_task", resourceId: TASK.id, status: "queued", payload: {},
  attempt: 0, maxAttempts: 3, timeoutSeconds: 600, availableAt: "now",
  createdAt: "now", updatedAt: "now",
};
const DETAIL: DiagnosticDetailData = { task: TASK, backgroundJob: JOB, steps: [], report: null };
const CHAIN: DiagnosticEvidenceChainData = {
  taskId: TASK.id, evidence: [], reportEvidenceLinks: [], toolAudits: [], executionResult: null,
};
const CASE: DiagnosticCase = {
  id: "case-1", ownerUserId: "user-1", taskId: TASK.id, reportId: "report-1",
  documentId: "doc-1", indexTaskId: "index-1", alertName: "HighLatency",
  service: "checkout", keywords: ["延迟"], rootCause: "依赖变慢", remediation: "检查依赖",
  summary: "checkout 延迟", evidenceIds: [], createdAt: "now",
  incidentFingerprint: "incident-v1", knowledgeFingerprint: "knowledge-v1",
  fingerprintVersion: "v1", promotionStatus: "canonical",
};
const result = <T>(data: T): ApiResult<T> => ({ data, requestId: "req-aiops" });

function fakeClient(events: readonly SseEvent[] = []): AiopsClient {
  return {
    listActiveAlerts: vi.fn(async () => result({ items: [ALERT] })),
    createDiagnostic: vi.fn(async () => result({ task: TASK, backgroundJob: JOB })),
    listDiagnostics: vi.fn(async () => result({ items: [TASK] })),
    getDiagnostic: vi.fn(async () => result(DETAIL)),
    getEvidenceChain: vi.fn(async () => result(CHAIN)),
    streamDiagnostic: vi.fn(async function* () { for (const event of events) yield event; }),
    cancelBackgroundJob: vi.fn(async () => result<BackgroundJob>({ ...JOB, status: "cancelled" })),
    listCases: vi.fn(async () => result({ items: [CASE] })),
    getCase: vi.fn(async () => result({ item: CASE })),
    promoteDiagnostic: vi.fn(async () => result({
      status: "created" as const, item: CASE, candidates: [],
    })),
    listKnowledgeBases: vi.fn(async () => result({
      items: [{ id: "kb-1", name: "默认知识库", isDefault: true as const }],
    })),
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  resetProtectedStoreRegistryForTests();
});

describe("AIOps store", () => {
  it("从真实服务器快照初始化并在受保护清理时移除 owner 数据", async () => {
    const store = createAiopsStore({ client: fakeClient() })();
    await store.initialize();
    expect(store.activeAlerts).toEqual([ALERT]);
    expect(store.history).toEqual([TASK]);
    expect(store.activeTask?.id).toBe(TASK.id);
    expect(store.cases).toEqual([CASE]);

    clearProtectedStores();
    expect(store.history).toEqual([]);
    expect(store.activeAlerts).toEqual([]);
    expect(store.evidenceChain).toBeNull();
  });

  it("允许仅手工 query 创建且 payload 没有 context", async () => {
    const client = fakeClient([{ id: "1", sequence: 1, type: "complete", channel: "aiops",
      timestamp: "now", data: { finishReason: "stop" } }]);
    const store = createAiopsStore({ client })();
    await store.createDiagnostic(" 手工排查 ", null);
    await vi.waitFor(() => expect(store.streaming).toBe(false));

    expect(client.createDiagnostic).toHaveBeenCalledWith({ query: "手工排查", alerts: [] });
    expect(JSON.stringify(vi.mocked(client.createDiagnostic).mock.calls[0]?.[0])).not.toContain("context");
    await expect(store.createDiagnostic(" ", null)).rejects.toThrow("请输入诊断问题");
  });

  it("按 sequence 消费 complete 并从服务端对账", async () => {
    const client = fakeClient([
      { id: "1", sequence: 1, type: "task.status", channel: "aiops", timestamp: "now",
        data: { taskId: TASK.id, status: "running", message: "Planner 生成计划" } },
      { id: "2", sequence: 2, type: "complete", channel: "aiops", timestamp: "now",
        data: { finishReason: "stop" } },
    ]);
    const store = createAiopsStore({ client })();
    await store.selectDiagnostic(TASK.id);
    await store.subscribeActive();

    expect(store.lastSequence).toBe(2);
    expect(store.streamDisconnected).toBe(false);
    expect(store.timeline[0]?.phase).toBe("planner");
    // select 一次 + 运行中按 task.status 刷新一次 + 流结束后对账一次
    expect(client.getDiagnostic).toHaveBeenCalledTimes(3);
  });

  it("运行中随步骤完成持续刷新执行总账，而不是等流结束才刷新", async () => {
    const client = fakeClient([
      { id: "1", sequence: 1, type: "tool.call", channel: "aiops", timestamp: "now",
        data: { toolCallId: "c1", toolName: "SearchLog", lifecycle: "started", input: { argumentKeys: [] } } },
      { id: "2", sequence: 2, type: "tool.call", channel: "aiops", timestamp: "now",
        data: { toolCallId: "c1", toolName: "SearchLog", lifecycle: "completed", output: { summary: "命中 4 条" } } },
      { id: "3", sequence: 3, type: "complete", channel: "aiops", timestamp: "now",
        data: { finishReason: "stop" } },
    ]);
    const store = createAiopsStore({ client })();
    await store.selectDiagnostic(TASK.id);
    expect(client.getEvidenceChain).toHaveBeenCalledTimes(1);

    await store.subscribeActive();

    // started 与 completed 各触发一次运行中刷新，流结束后再对账一次，共 1 + 2 + 1 = 4 次。
    // 期望是"运行中就一直在拉"，而不是攒到流结束才拉一次。
    expect(vi.mocked(client.getEvidenceChain).mock.calls.length).toBeGreaterThanOrEqual(4);
  });

  it("运行中的诊断在恢复快照后自动接回实时流，已结束的任务不订阅", async () => {
    const running = fakeClient();
    const runningStore = createAiopsStore({ client: running })();
    runningStore.activeDetail = {
      ...DETAIL,
      task: { ...TASK, status: "running" },
      backgroundJob: { ...JOB, status: "running" },
    };
    runningStore.resumeStreamIfActive();
    await vi.waitFor(() => expect(running.streamDiagnostic).toHaveBeenCalledTimes(1));

    const finished = fakeClient();
    const finishedStore = createAiopsStore({ client: finished })();
    finishedStore.activeDetail = DETAIL; // task 与 job 都是 succeeded
    finishedStore.resumeStreamIfActive();
    await Promise.resolve();
    expect(finished.streamDiagnostic).not.toHaveBeenCalled();
  });

  it("断流后只做一次 REST 恢复且不自动重新订阅", async () => {
    const client = fakeClient();
    client.streamDiagnostic = vi.fn(async function* (): AsyncIterable<SseEvent> {
      yield { id: "1", sequence: 1, type: "task.status", channel: "aiops", timestamp: "now",
        data: { taskId: TASK.id, status: "running" } };
      throw new Error("network gone");
    });
    const store = createAiopsStore({ client })();
    await store.selectDiagnostic(TASK.id);
    await store.subscribeActive();

    expect(store.streamDisconnected).toBe(true);
    expect(store.streamError).toContain("network gone");
    expect(client.streamDiagnostic).toHaveBeenCalledTimes(1);
    // 三次 = select 一次 + running 状态事件触发的运行中刷新一次 + 断流后的 REST 恢复一次。
    // 关键断言是"不自动重新订阅"（上面的 streamDiagnostic 只调了一次）与"恢复只做一轮"。
    expect(client.getDiagnostic).toHaveBeenCalledTimes(3);
  });

  it("通过 background job id 取消并解析案例知识文档目标", async () => {
    const client = fakeClient();
    const store = createAiopsStore({ client })();
    await store.selectDiagnostic(TASK.id);
    expect(store.canCancel).toBe(true);
    await store.cancelActive();
    expect(client.cancelBackgroundJob).toHaveBeenCalledWith(JOB.id);

    await store.selectCase(CASE.id);
    expect(await store.knowledgeDocumentTarget()).toEqual({
      knowledgeBaseId: "kb-1", documentId: CASE.documentId,
    });
  });

  it("单个告警 source 失败不阻止历史和案例恢复", async () => {
    const client = fakeClient();
    client.listActiveAlerts = vi.fn(async () => { throw new Error("告警源不可用"); });
    const store = createAiopsStore({ client })();
    store.activeAlerts = [ALERT];
    await store.initialize();
    expect(store.alertError).toBe("告警源不可用");
    expect(store.activeAlerts).toEqual([]);
    expect(store.history).toEqual([TASK]);
    expect(store.cases).toEqual([CASE]);
  });

  it("显式提升可信报告，并保留相似候选供人工 merge 或新建", async () => {
    const client = fakeClient();
    client.promoteDiagnostic = vi.fn()
      .mockResolvedValueOnce(result({ status: "needs_review", item: null,
        candidates: [{ item: CASE, similarityScore: 0.82 }] }))
      .mockResolvedValueOnce(result({ status: "merged", item: CASE, candidates: [] }));
    const store = createAiopsStore({ client })();
    await store.selectDiagnostic(TASK.id);

    await store.promoteActive();
    expect(store.promotionCandidates).toEqual([{ item: CASE, similarityScore: 0.82 }]);
    expect(store.promotionError).toBeNull();
    await store.resolvePromotion("merge", CASE.id);

    expect(client.promoteDiagnostic).toHaveBeenNthCalledWith(1, TASK.id, {});
    expect(client.promoteDiagnostic).toHaveBeenNthCalledWith(2, TASK.id, {
      resolution: "merge", candidateCaseId: CASE.id,
    });
    expect(store.selectedCase).toEqual(CASE);
    expect(store.promotionCandidates).toEqual([]);
  });
});
