import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";

import type {
  ActiveAlert,
  DiagnosticCase,
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
  DiagnosticTask,
  SseEvent,
} from "@super-ai/api-contracts";

import { createAiopsClient } from "../aiops/aiopsClient";
import type { AiopsClient } from "../aiops/aiopsClient";
import { buildLiveTimeline, buildPersistentExecutionChain } from "../aiops/timeline";
import type { AiopsTimelineItem } from "../aiops/timeline";
import { publicConfig } from "../config";
import { createApiClient } from "../transport/apiClient";
import { createSseClient } from "../transport/sseClient";
import { AUTH_TOKEN_STORAGE_KEY, useAuthStore } from "./auth";
import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

const CANCELLABLE_JOB_STATUSES = new Set(["queued", "running"]);

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
    const executionChain = shallowRef<readonly AiopsTimelineItem[]>([]);

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
      executionChain.value = buildPersistentExecutionChain(detail.data, chain.data);
      liveEvents.value = [];
      timeline.value = [];
      lastSequence.value = 0;
      streamDisconnected.value = false;
      streamError.value = null;
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
          taskId: created.data.task.id, evidence: [], reportEvidenceLinks: [], toolAudits: [],
        };
        executionChain.value = [];
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
      try {
        for await (const event of dependencies.client.streamDiagnostic(taskId, lastSequence.value)) {
          if (expectedGeneration !== generation || expectedStream !== streamGeneration) return;
          if (event.channel !== "aiops" || event.sequence <= lastSequence.value) continue;
          liveEvents.value = [...liveEvents.value, event];
          timeline.value = buildLiveTimeline(liveEvents.value);
          lastSequence.value = event.sequence;
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
      executionChain.value = buildPersistentExecutionChain(activeDetail.value, evidenceChain.value);
      if (listed.status === "fulfilled") history.value = listed.value.data.items;
      if (caseList.status === "fulfilled") cases.value = caseList.value.data.items;
      if ([detail, chain, listed, caseList].every((result) => result.status === "rejected")) {
        dataError.value = "持久状态恢复失败，请稍后重试";
      }
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
      liveEvents.value = [];
      timeline.value = [];
      executionChain.value = [];
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
      history, activeAlerts, cases, activeDetail, evidenceChain, selectedCase, liveEvents,
      loading, creating, streaming, streamDisconnected, dataError, alertError, streamError,
      lastSequence, activeTask, activeJob, canCancel, timeline, executionChain,
      initialize, refreshAlerts, refreshHistory, refreshCases, selectDiagnostic,
      createDiagnostic, subscribeActive, reconcileActive, cancelActive, selectCase,
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
