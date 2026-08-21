<script setup lang="ts">
import { Ban, Radio, RotateCw } from "lucide-vue-next";
import { computed } from "vue";

import type { DiagnosticDetailData } from "@super-ai/api-contracts";

import type { AiopsTimelineItem } from "../../aiops/timeline";
import { renderSafeMarkdown } from "../../chat/renderSafeMarkdown";
import UserFeedbackControl from "../feedback/UserFeedbackControl.vue";

const props = defineProps<{
  detail: DiagnosticDetailData | null;
  timeline: readonly AiopsTimelineItem[];
  streaming: boolean;
  disconnected: boolean;
  streamError: string | null;
  canCancel: boolean;
}>();
defineEmits<{ cancel: []; subscribe: [] }>();

const reportHtml = computed(() => renderSafeMarkdown(props.detail?.report?.markdown ?? ""));
const diagnosticStatus = computed(() => props.detail?.task.status ?? "未选择");
const jobStatus = computed(() => props.detail?.backgroundJob.status ?? "未选择");

function phaseLabel(phase: AiopsTimelineItem["phase"]): string {
  return ({ planner: "Planner", executor: "Executor", replanner: "Replanner", report: "Report", task: "任务" })[phase];
}

function statusLabel(status: string): string {
  return ({ accepted: "已受理", queued: "排队中", running: "运行中", succeeded: "已成功", failed: "失败", cancelled: "已取消" } as Record<string, string>)[status] ?? status;
}
</script>

<template>
  <section class="aiops-column aiops-center" aria-label="当前报告与实时 timeline">
    <header class="center-heading">
      <div><p class="eyebrow">CURRENT DIAGNOSIS</p><h2>{{ detail?.task.query || detail?.task.alerts[0]?.alertName || "选择或创建诊断" }}</h2></div>
      <div class="status-pair" aria-label="诊断与后台任务状态"><span>诊断：<strong>{{ statusLabel(diagnosticStatus) }} ({{ diagnosticStatus }})</strong></span><span>后台任务：<strong>{{ statusLabel(jobStatus) }} ({{ jobStatus }})</strong></span></div>
    </header>
    <div class="stream-controls">
      <span v-if="streaming" role="status"><Radio :size="14" aria-hidden="true" />正在读取持久事件</span>
      <span v-else-if="disconnected" class="stream-warning" role="alert">{{ streamError }}</span>
      <span v-else class="muted">实时流未连接</span>
      <button v-if="disconnected && detail && !['succeeded','failed','cancelled'].includes(detail.task.status)" type="button" @click="$emit('subscribe')"><RotateCw :size="14" aria-hidden="true" />手动重新订阅</button>
      <button v-if="canCancel" type="button" @click="$emit('cancel')"><Ban :size="14" aria-hidden="true" />取消后台任务</button>
    </div>

    <div class="center-body">
      <section class="report-panel">
        <header><strong>诊断报告</strong><span v-if="detail?.report">{{ detail.report.uncertainty ? "包含不确定性" : "证据已关联" }} · {{ detail.report.generationMode === "fallback" ? "诚实 fallback" : "模型生成" }}</span></header>
        <div v-if="detail?.report" class="aiops-report-scroll">
          <div class="markdown-body" v-html="reportHtml" />
          <UserFeedbackControl
            target-type="diagnostic_report"
            :target-id="detail.report.id"
            :subject-id="null"
          />
        </div>
        <div v-else class="blank-report">最终报告将在持久任务成功后显示；失败不会伪装为成功。</div>
      </section>
      <section class="timeline-panel">
        <header><strong>实时 Timeline</strong><span>phase 不是任务状态</span></header>
        <div v-if="timeline.length" class="timeline-scroll" aria-label="实时诊断 timeline">
          <article v-for="entry in timeline" :key="entry.key" class="timeline-item" :data-status="entry.status">
            <div><span>{{ phaseLabel(entry.phase) }}</span><strong>{{ entry.title }}</strong><time v-if="entry.timestamp">{{ entry.timestamp }}</time></div>
            <p>{{ entry.summary }}</p>
            <details v-if="entry.collapsible && entry.detail"><summary>查看安全摘要</summary><p>{{ entry.detail }}</p></details>
          </article>
        </div>
        <p v-else class="muted timeline-empty">尚无实时持久事件</p>
      </section>
    </div>
  </section>
</template>

<style scoped>
.aiops-column { min-width: 0; min-height: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); overflow: hidden; }.aiops-center { display: grid; grid-template-rows: auto auto minmax(0, 1fr); }.center-heading { min-width: 0; display: flex; justify-content: space-between; gap: 12px; padding: 14px 16px 10px; border-bottom: 1px solid var(--color-border); }.center-heading h2 { max-width: 550px; margin: 2px 0 0; overflow: hidden; font-size: 18px; text-overflow: ellipsis; white-space: nowrap; }.status-pair { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; justify-content: flex-end; }.status-pair span { border: 1px solid var(--color-border); border-radius: 999px; padding: 5px 8px; color: var(--color-text-muted); font-size: 10px; }.status-pair strong { color: var(--color-text); }.stream-controls { min-height: 42px; display: flex; align-items: center; gap: 8px; padding: 7px 14px; border-bottom: 1px solid var(--color-border); font-size: 11px; }.stream-controls span { margin-right: auto; display: flex; align-items: center; gap: 5px; }.stream-controls button { min-height: 30px; border: 1px solid var(--color-border); border-radius: 7px; display: inline-flex; align-items: center; gap: 5px; background: white; cursor: pointer; }.stream-warning { color: var(--color-danger); }.muted { color: var(--color-text-muted); }.center-body { min-height: 0; display: grid; grid-template-rows: minmax(240px, 1.15fr) minmax(170px, .85fr); }.report-panel,.timeline-panel { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); }.report-panel { border-bottom: 1px solid var(--color-border); }.report-panel > header,.timeline-panel > header { display: flex; justify-content: space-between; padding: 10px 14px; }.report-panel header span,.timeline-panel header span { color: var(--color-text-muted); font-size: 10px; }.aiops-report-scroll,.timeline-scroll { min-height: 0; overflow: auto; }.aiops-report-scroll { padding: 0 18px 20px; line-height: 1.65; }.blank-report { padding: 32px 18px; color: var(--color-text-muted); font-size: 12px; }.timeline-scroll { padding: 0 12px 12px; }.timeline-item { position: relative; border-left: 2px solid #b8cdc7; padding: 6px 0 10px 12px; }.timeline-item[data-status="failed"] { border-left-color: var(--color-danger); }.timeline-item > div { display: flex; align-items: baseline; gap: 7px; }.timeline-item div > span { min-width: 64px; color: var(--color-accent); font-size: 10px; font-weight: 700; }.timeline-item time { margin-left: auto; color: var(--color-text-muted); font-size: 9px; }.timeline-item p { margin: 4px 0 0; color: var(--color-text-muted); font-size: 11px; line-height: 1.5; }.timeline-item details summary { margin-top: 5px; color: var(--color-accent); cursor: pointer; font-size: 10px; }.timeline-empty { padding: 12px 14px; font-size: 11px; }
:deep(.markdown-body img) { max-width: 100%; }:deep(.markdown-body pre) { max-width: 100%; overflow: auto; }:deep(.markdown-body table) { display: block; max-width: 100%; overflow: auto; }
</style>
