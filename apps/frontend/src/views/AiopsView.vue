<script setup lang="ts">
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
  // 刷新页面会丢掉上一次的实时流：恢复快照后如果这条诊断还在跑，就自动接回去，
  // 不要求用户"重新刷新"或手点"手动重新订阅"才能继续看到耗时和步骤状态。
  store.resumeStreamIfActive();
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
  try { await store.selectDiagnostic(id); store.resumeStreamIfActive(); }
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

async function promote(): Promise<void> {
  try { await store.promoteActive(); feedback.show("success", "案例提升请求已处理"); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "案例提升失败"); }
}

async function resolvePromotion(
  resolution: "create_new" | "merge", candidateCaseId: string,
): Promise<void> {
  try { await store.resolvePromotion(resolution, candidateCaseId); feedback.show("success", "相似案例决策已保存"); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "案例决策失败"); }
}
</script>

<template>
  <div class="aiops-workspace" data-route-canvas="aiops">
    <!-- 页面标题由布局层的 h1 提供；这里不再重复一遍控制台标题与说明，把纵向空间留给三栏工作区。 -->
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
        :execution="store.evidenceChain?.executionResult ?? null"
        :disconnected="store.streamDisconnected" :stream-error="store.streamError" :can-cancel="store.canCancel"
        :promotion-candidates="store.promotionCandidates" :promotion-error="store.promotionError"
        :promoting="store.promoting"
        @cancel="cancel" @subscribe="store.subscribeActive()" @promote="promote"
        @resolve-promotion="resolvePromotion"
      />
      <AiopsEvidenceCases
        :detail="store.activeDetail" :chain="store.evidenceChain"
        :cases="store.cases" :selected-case="store.selectedCase"
        @select-case="selectCase" @open-document="openDocument" @refresh-cases="refreshCases"
      />
    </main>
  </div>
</template>

<style scoped>
.aiops-workspace { height: calc(100vh - 74px); min-width: 0; min-height: 0; display: grid; grid-template-rows: minmax(0, 1fr); gap: 12px; padding: 14px; overflow: hidden; background: #f4f7f6; }.aiops-grid { min-width: 0; min-height: 0; display: grid; grid-template-columns: minmax(250px, .82fr) minmax(430px, 1.65fr) minmax(270px, .9fr); gap: 12px; overflow: hidden; }
</style>
