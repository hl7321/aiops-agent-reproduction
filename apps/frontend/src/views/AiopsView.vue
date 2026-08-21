<script setup lang="ts">
import { Activity } from "lucide-vue-next";
import { onBeforeUnmount, onMounted } from "vue";
import { useRouter } from "vue-router";

import type { ActiveAlert } from "@super-ai/api-contracts";

import AiopsEvidenceCases from "../components/aiops/AiopsEvidenceCases.vue";
import AiopsInputHistory from "../components/aiops/AiopsInputHistory.vue";
import AiopsReportTimeline from "../components/aiops/AiopsReportTimeline.vue";
import AppErrorState from "../components/states/AppErrorState.vue";
import AppLoadingState from "../components/states/AppLoadingState.vue";
import { useAiopsStore } from "../stores/aiops";
import { useFeedbackStore } from "../stores/feedback";

const store = useAiopsStore();
const feedback = useFeedbackStore();
const router = useRouter();

onMounted(async () => {
  try { await store.initialize(); }
  catch { /* store 按真实数据域提供安全错误。 */ }
});
onBeforeUnmount(() => store.reset());

async function create(query: string, alert: ActiveAlert | null): Promise<void> {
  try {
    await store.createDiagnostic(query, alert);
    feedback.show("success", "持久诊断任务已创建");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "诊断创建失败");
  }
}

async function selectTask(id: string): Promise<void> {
  try { await store.selectDiagnostic(id); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "诊断读取失败"); }
}

async function cancel(): Promise<void> {
  try { await store.cancelActive(); feedback.show("info", "已向后台任务提交取消请求"); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "取消失败"); }
}

async function refreshAlerts(): Promise<void> {
  try { await store.refreshAlerts(); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "活跃告警刷新失败"); }
}

async function refreshCases(): Promise<void> {
  try { await store.refreshCases(); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "案例库刷新失败"); }
}

async function selectCase(id: string): Promise<void> {
  try { await store.selectCase(id); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "案例读取失败"); }
}

async function openDocument(): Promise<void> {
  try {
    const target = await store.knowledgeDocumentTarget();
    await router.push({ name: "knowledge", query: target });
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "知识文档不可用");
  }
}
</script>

<template>
  <div class="aiops-workspace" data-route-canvas="aiops">
    <header class="aiops-heading">
      <div class="aiops-heading__icon"><Activity :size="21" aria-hidden="true" /></div>
      <div><p class="eyebrow">AIOPS</p><h1>智能诊断控制台</h1><p>真实告警、持久任务、证据与案例均来自服务器。</p></div>
    </header>
    <AppLoadingState v-if="store.loading && store.history.length === 0" message="正在恢复持久诊断状态" />
    <AppErrorState v-else-if="store.dataError && store.history.length === 0" :message="store.dataError" />
    <main v-else class="aiops-grid">
      <AiopsInputHistory
        :alerts="store.activeAlerts" :history="store.history" :selected-task-id="store.activeTask?.id ?? null"
        :alert-error="store.alertError" :creating="store.creating"
        @create="create" @refresh-alerts="refreshAlerts" @select-task="selectTask"
      />
      <AiopsReportTimeline
        :detail="store.activeDetail" :timeline="store.timeline" :streaming="store.streaming"
        :disconnected="store.streamDisconnected" :stream-error="store.streamError" :can-cancel="store.canCancel"
        @cancel="cancel" @subscribe="store.subscribeActive()"
      />
      <AiopsEvidenceCases
        :detail="store.activeDetail" :chain="store.evidenceChain" :execution-chain="store.executionChain"
        :cases="store.cases" :selected-case="store.selectedCase"
        @select-case="selectCase" @open-document="openDocument" @refresh-cases="refreshCases"
      />
    </main>
  </div>
</template>

<style scoped>
.aiops-workspace { height: calc(100vh - 74px); min-width: 0; min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 12px; padding: 14px; overflow: hidden; background: #f4f7f6; }.aiops-heading { min-width: 0; display: flex; align-items: center; gap: 10px; }.aiops-heading__icon { width: 40px; height: 40px; border: 1px solid #cfe0db; border-radius: 11px; display: grid; place-items: center; color: var(--color-accent); background: var(--color-accent-soft); }.aiops-heading h1 { margin: 1px 0; font-size: 20px; }.aiops-heading p:last-child { margin: 0; color: var(--color-text-muted); font-size: 11px; }.aiops-grid { min-width: 0; min-height: 0; display: grid; grid-template-columns: minmax(250px, .82fr) minmax(430px, 1.65fr) minmax(270px, .9fr); gap: 12px; overflow: hidden; }
</style>
