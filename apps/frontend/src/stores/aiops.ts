import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";

import type {
  ActiveAlert,
  DiagnosticCase,
  DiagnosticCasePromotionCandidate,
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
  DiagnosticTask,
  SseEvent,
} from "@super-ai/api-contracts";

import { createAiopsClient } from "../aiops/aiopsClient";
import type { AiopsClient } from "../aiops/aiopsClient";
import { buildLiveTimeline } from "../aiops/timeline";
import type { AiopsTimelineItem } from "../aiops/timeline";
import { publicConfig } from "../config";
import { createApiClient } from "../transport/apiClient";
import { createSseClient } from "../transport/sseClient";
import { AUTH_TOKEN_STORAGE_KEY, useAuthStore } from "./auth";
import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

const CANCELLABLE_JOB_STATUSES = new Set(["queued", "running"]);

/**
 * 诊断运行期间"对账数据"的兜底刷新间隔（毫秒）。
 *
 * 后端在模型思考和执行长工具时没有事件可发，只靠 SSE 事件驱动的话页面会长时间不动，
 * 用户以为卡死。这里约定一个偏慢但不会停的节拍，配合事件驱动的即时刷新。
 */
const LIVE_REFRESH_INTERVAL_MS = 4_000;

export interface AiopsStoreDependencies {
  readonly client: AiopsClient;
}

export function createAiopsStore(dependencies: AiopsStoreDependencies) {
  return defineStore("aiops", () => {
    const history = ref<readonly DiagnosticTask[]>([]);
    const activeAlerts = ref<readonly ActiveAlert[]>([]);
    const cases = ref<readonly DiagnosticCase[]>([]);
    const activeDetail = ref<DiagnosticDetailData | null>(null);
    const evidenceChain = ref<DiagnosticEvidenceChainData | null>(null);
    const selectedCase = ref<DiagnosticCase | null>(null);
    const promotionCandidates = ref<readonly DiagnosticCasePromotionCandidate[]>([]);
    const promotionError = ref<string | null>(null);
    const promoting = ref(false);
    const liveEvents = shallowRef<readonly SseEvent[]>([]);
    const loading = ref(false);
    const creating = ref(false);
    const streaming = ref(false);
    const streamDisconnected = ref(false);
    const dataError = ref<string | null>(null);
    const alertError = ref<string | null>(null);
    const streamError = ref<string | null>(null);
    const lastSequence = ref(0);
    let generation = 0;
    let streamGeneration = 0;

    const activeTask = computed(() => activeDetail.value?.task ?? null);
    const activeJob = computed(() => activeDetail.value?.backgroundJob ?? null);
    const canCancel = computed(() => activeJob.value !== null
      && CANCELLABLE_JOB_STATUSES.has(activeJob.value.status));
    const timeline = shallowRef<readonly AiopsTimelineItem[]>([]);

    async function initialize(): Promise<void> {
      const expectedGeneration = generation;
      loading.value = true;
      dataError.value = null;
      const [alertsResult, historyResult, casesResult] = await Promise.allSettled([
        refreshAlerts(expectedGeneration),
        refreshHistory(expectedGeneration),
        refreshCases(expectedGeneration),
      ]);
      if (expectedGeneration !== generation) return;
      if (alertsResult.status === "rejected") alertError.value = message(alertsResult.reason, "活跃告警读取失败");
      const coreFailure = [historyResult, casesResult].find((result) => result.status === "rejected");
      if (coreFailure?.status === "rejected") dataError.value = message(coreFailure.reason, "诊断数据读取失败");
      const first = history.value[0];
      if (first !== undefined) {
        try { await selectDiagnostic(first.id); }
        catch (error: unknown) { dataError.value = message(error, "诊断详情读取失败"); }
      }
      if (expectedGeneration === generation) loading.value = false;
    }

    async function refreshAlerts(expectedGeneration = generation): Promise<void> {
      try {
        const response = await dependencies.client.listActiveAlerts();
        if (expectedGeneration === generation) {
          activeAlerts.value = response.data.items;
          alertError.value = null;
        }
      } catch (error: unknown) {
        if (expectedGeneration === generation) {
          activeAlerts.value = [];
          alertError.value = message(error, "活跃告警读取失败");
        }
        throw error;
      }
    }

    async function refreshHistory(expectedGeneration = generation): Promise<void> {
      const response = await dependencies.client.listDiagnostics();
      if (expectedGeneration === generation) history.value = response.data.items;
    }

    async function refreshCases(expectedGeneration = generation): Promise<void> {
      const response = await dependencies.client.listCases();
      if (expectedGeneration === generation) cases.value = response.data.items;
    }

    async function selectDiagnostic(id: string): Promise<void> {
      const expectedGeneration = generation;
      const [detail, chain] = await Promise.all([
        dependencies.client.getDiagnostic(id), dependencies.client.getEvidenceChain(id),
      ]);
      if (expectedGeneration !== generation) return;
      activeDetail.value = detail.data;
      evidenceChain.value = chain.data;
      liveEvents.value = [];
      timeline.value = [];
      lastSequence.value = 0;
      streamDisconnected.value = false;
      streamError.value = null;
      promotionCandidates.value = [];
      promotionError.value = null;
    }

    async function createDiagnostic(query: string, alert: ActiveAlert | null): Promise<void> {
      const normalizedQuery = query.trim();
      if (!normalizedQuery && alert === null) throw new Error("请输入诊断问题或选择一条真实告警");
      const expectedGeneration = generation;
      creating.value = true;
      dataError.value = null;
      try {
        const created = await dependencies.client.createDiagnostic({
          alerts: alert === null ? [] : [alert],
          ...(normalizedQuery ? { query: normalizedQuery } : {}),
        });
        if (expectedGeneration !== generation) return;
        activeDetail.value = {
          task: created.data.task,
          backgroundJob: created.data.backgroundJob,
          steps: [],
          report: null,
        };
        evidenceChain.value = {
          taskId: created.data.task.id,
          evidence: [],
          reportEvidenceLinks: [],
          toolAudits: [],
          executionResult: null,
        };
        history.value = [created.data.task, ...history.value.filter((item) => item.id !== created.data.task.id)];
        liveEvents.value = [];
        timeline.value = [];
        lastSequence.value = 0;
        void subscribeActive();
      } catch (error: unknown) {
        if (expectedGeneration === generation) dataError.value = message(error, "诊断创建失败");
        throw error;
      } finally {
        if (expectedGeneration === generation) creating.value = false;
      }
    }

    async function subscribeActive(): Promise<void> {
      const taskId = activeTask.value?.id;
      if (taskId === undefined || streaming.value) return;
      const expectedGeneration = generation;
      const expectedStream = ++streamGeneration;
      streaming.value = true;
      streamDisconnected.value = false;
      streamError.value = null;
      let sawComplete = false;
      // 执行总账必须"边走边更新"，而不是等整条流结束才刷一次。这里两条路一起用：
      // 1) 事件驱动：每来一条工具调用（开始/结束/失败）、节点状态或报告事件，立刻拉一次最新对账数据；
      // 2) 心跳兜底：模型思考和长工具调用期间后端本来就没有事件可发（30 秒级静默很常见），
      //    所以再按固定间隔拉一次，保证页面上的耗时和阶段状态一直在往前走。
      // in-flight 标志避免请求堆叠；不做时间节流，方便测试直接断言调用次数。
      let refreshInFlight = false;
      const refreshLiveState = async (): Promise<void> => {
        if (refreshInFlight) return;
        refreshInFlight = true;
        try {
          const [detail, chain] = await Promise.allSettled([
            dependencies.client.getDiagnostic(taskId), dependencies.client.getEvidenceChain(taskId),
          ]);
          if (expectedGeneration !== generation || expectedStream !== streamGeneration) return;
          if (detail.status === "fulfilled") activeDetail.value = detail.value.data;
          if (chain.status === "fulfilled") evidenceChain.value = chain.value.data;
        } finally {
          refreshInFlight = false;
        }
      };
      // 离开页面（reset）或换了一条流之后，这个定时器就没有意义了，自己停掉，
      // 避免在后台继续对着旧任务发请求。
      const heartbeat = setInterval(() => {
        if (expectedGeneration !== generation || expectedStream !== streamGeneration) {
          clearInterval(heartbeat);
          return;
        }
        void refreshLiveState();
      }, LIVE_REFRESH_INTERVAL_MS);
      try {
        for await (const event of dependencies.client.streamDiagnostic(taskId, lastSequence.value)) {
          if (expectedGeneration !== generation || expectedStream !== streamGeneration) return;
          if (event.channel !== "aiops" || event.sequence <= lastSequence.value) continue;
          liveEvents.value = [...liveEvents.value, event];
          timeline.value = buildLiveTimeline(liveEvents.value);
          lastSequence.value = event.sequence;
          // 工具调用一开始就刷新：后端是先落 running 的步骤记录、再发 started 事件，
          // 所以此刻拉回来的执行总账里已经有"进行中 + startedAt"，
          // 前端秒表才能从这一步刚开始就往上走，而不是等它跑完才出现。
          if (event.type === "tool.call" || event.type === "task.status" || event.type === "report") {
            void refreshLiveState();
          }
          if (event.type === "complete") sawComplete = true;
        }
        if (!sawComplete && expectedGeneration === generation && expectedStream === streamGeneration) {
          streamDisconnected.value = true;
          streamError.value = "实时流已断开，已从服务器恢复持久状态；如需继续观察请手动重新订阅。";
        }
      } catch (error: unknown) {
        if (expectedGeneration === generation && expectedStream === streamGeneration) {
          streamDisconnected.value = true;
          streamError.value = message(error, "实时流已断开");
        }
      } finally {
        // 心跳必须无条件停掉：上面的早退分支会跳过 reconcile，
        // 如果只在同一个 if 里清理就会留下一个永远在轮询的定时器。
        clearInterval(heartbeat);
        if (expectedGeneration === generation && expectedStream === streamGeneration) {
          streaming.value = false;
          await reconcileActive(taskId, expectedGeneration);
        }
      }
    }

    async function reconcileActive(taskId: string, expectedGeneration = generation): Promise<void> {
      const [detail, chain, listed, caseList] = await Promise.allSettled([
        dependencies.client.getDiagnostic(taskId), dependencies.client.getEvidenceChain(taskId),
        dependencies.client.listDiagnostics(), dependencies.client.listCases(),
      ]);
      if (expectedGeneration !== generation || activeTask.value?.id !== taskId) return;
      if (detail.status === "fulfilled") activeDetail.value = detail.value.data;
      if (chain.status === "fulfilled") evidenceChain.value = chain.value.data;
      if (listed.status === "fulfilled") history.value = listed.value.data.items;
      if (caseList.status === "fulfilled") cases.value = caseList.value.data.items;
      if ([detail, chain, listed, caseList].every((result) => result.status === "rejected")) {
        dataError.value = "持久状态恢复失败，请稍后重试";
      }
    }

    /**
     * 选中的诊断还在跑、当前又没在订阅时，自动把实时流接回来。
     *
     * 场景是"刷新页面之后"：页面重新加载会丢掉上一次的 SSE 连接，
     * 以前必须让用户手点"手动重新订阅"才会继续更新。这里让它在恢复快照之后自动接回。
     * 已经结束的任务（succeeded / failed / cancelled）不订阅——不会再有新事件，订阅只会空转。
     */
    function resumeStreamIfActive(): void {
      const job = activeJob.value;
      if (job === null || !CANCELLABLE_JOB_STATUSES.has(job.status) || streaming.value) return;
      void subscribeActive();
    }

    async function cancelActive(): Promise<void> {
      const job = activeJob.value;
      const task = activeTask.value;
      if (job === null || task === null || !CANCELLABLE_JOB_STATUSES.has(job.status)) return;
      await dependencies.client.cancelBackgroundJob(job.id);
      await reconcileActive(task.id);
    }

    async function selectCase(id: string): Promise<void> {
      selectedCase.value = (await dependencies.client.getCase(id)).data.item;
    }

    async function promoteActive(): Promise<void> {
      const task = activeTask.value;
      if (task === null) throw new Error("未选择诊断任务");
      await promote(task.id, {});
    }

    async function resolvePromotion(
      resolution: "create_new" | "merge", candidateCaseId: string,
    ): Promise<void> {
      const task = activeTask.value;
      if (task === null) throw new Error("未选择诊断任务");
      await promote(task.id, { resolution, candidateCaseId });
    }

    async function promote(
      taskId: string,
      body: { readonly resolution?: "create_new" | "merge"; readonly candidateCaseId?: string },
    ): Promise<void> {
      promoting.value = true;
      promotionError.value = null;
      try {
        const response = await dependencies.client.promoteDiagnostic(taskId, body);
        promotionCandidates.value = response.data.candidates;
        const item = response.data.item;
        if (item !== null) {
          selectedCase.value = item;
          cases.value = [item, ...cases.value.filter((candidate) => candidate.id !== item.id)];
        }
      } catch (error: unknown) {
        promotionError.value = message(error, "诊断案例提升失败");
        throw error;
      } finally {
        promoting.value = false;
      }
    }

    async function knowledgeDocumentTarget(item = selectedCase.value): Promise<{
      readonly knowledgeBaseId: string; readonly documentId: string;
    }> {
      if (item === null) throw new Error("未选择诊断案例");
      const bases = await dependencies.client.listKnowledgeBases();
      const knowledgeBaseId = bases.data.items[0]?.id;
      if (knowledgeBaseId === undefined) throw new Error("没有可用的知识库");
      return { knowledgeBaseId, documentId: item.documentId };
    }

    function reset(): void {
      generation += 1;
      streamGeneration += 1;
      history.value = [];
      activeAlerts.value = [];
      cases.value = [];
      activeDetail.value = null;
      evidenceChain.value = null;
      selectedCase.value = null;
      promotionCandidates.value = [];
      promotionError.value = null;
      promoting.value = false;
      liveEvents.value = [];
      timeline.value = [];
      loading.value = false;
      creating.value = false;
      streaming.value = false;
      streamDisconnected.value = false;
      dataError.value = null;
      alertError.value = null;
      streamError.value = null;
      lastSequence.value = 0;
    }

    registerProtectedStoreCleanup(reset);
    return {
      history, activeAlerts, cases, activeDetail, evidenceChain, selectedCase,
      promotionCandidates, promotionError, promoting, liveEvents,
      loading, creating, streaming, streamDisconnected, dataError, alertError, streamError,
      lastSequence, activeTask, activeJob, canCancel, timeline,
      initialize, refreshAlerts, refreshHistory, refreshCases, selectDiagnostic,
      createDiagnostic, subscribeActive, resumeStreamIfActive, reconcileActive, cancelActive, selectCase,
      promoteActive, resolvePromotion,
      knowledgeDocumentTarget, reset,
    };
  });
}

function message(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

const transportOptions = {
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => useAuthStore().clearLocalState(),
};
const browserClient = createAiopsClient(
  createApiClient(transportOptions), createSseClient(transportOptions),
);

export const useAiopsStore = createAiopsStore({ client: browserClient });
