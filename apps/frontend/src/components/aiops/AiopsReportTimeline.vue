<script setup lang="ts">
import { Ban, Radio, RotateCw } from "lucide-vue-next";
import { computed, ref } from "vue";

import type {
  DiagnosticCasePromotionCandidate,
  DiagnosticDetailData,
  DiagnosticExecutionResult,
} from "@super-ai/api-contracts";

import type { AiopsTimelineItem } from "../../aiops/timeline";
import { diagnosticStatusLabel } from "../../aiops/status";
import { renderSafeMarkdown } from "../../chat/renderSafeMarkdown";
import { useUserFeedbackStore } from "../../stores/userFeedback";
import UserFeedbackControl from "../feedback/UserFeedbackControl.vue";
import AiopsExecutionLedger from "./AiopsExecutionLedger.vue";

const props = defineProps<{
  detail: DiagnosticDetailData | null;
  execution: DiagnosticExecutionResult | null;
  timeline: readonly AiopsTimelineItem[];
  streaming: boolean;
  disconnected: boolean;
  streamError: string | null;
  canCancel: boolean;
  promotionCandidates: readonly DiagnosticCasePromotionCandidate[];
  promotionError: string | null;
  promoting: boolean;
}>();
defineEmits<{
  cancel: [];
  subscribe: [];
  promote: [];
  resolvePromotion: [resolution: "create_new" | "merge", candidateCaseId: string];
}>();

const userFeedback = useUserFeedbackStore();

const reportHtml = computed(() => renderSafeMarkdown(props.detail?.report?.markdown ?? ""));
const diagnosticStatus = computed(() => props.detail?.task.status ?? "未选择");
const jobStatus = computed(() => props.detail?.backgroundJob.status ?? "未选择");
// 诊断终态表达的是"有没有得出可信结论"，不是"流程有没有走完"：
// 证据不足的任务会落到 failed + 专用错误码，这里据此与系统故障区分展示。
const diagnosticStatusText = computed(() => diagnosticStatusLabel(props.detail?.task));
const reportTrustLabel = computed(() => {
  const state = props.detail?.report?.trustState;
  if (state === "verified_evidence") return "可信证据已验证";
  if (state === "execution_failed") return "执行失败，不可沉淀";
  if (state === "insufficient_evidence") return "证据不足，不可沉淀";
  return "尚无可信报告";
});
const positiveApproval = computed(() => {
  const report = props.detail?.report;
  return report !== null && report !== undefined
    && userFeedback.find("diagnostic_report", report.id, null)?.rating === "positive";
});
const canPromote = computed(() => props.detail?.report?.trustState === "verified_evidence"
  && props.detail.report.uncertainty === false && positiveApproval.value);

function phaseLabel(phase: AiopsTimelineItem["phase"]): string {
  return ({ planner: "Planner", executor: "Executor", replanner: "Replanner", report: "Report", task: "任务" })[phase];
}

function statusLabel(status: string): string {
  return ({ accepted: "已受理", queued: "排队中", running: "运行中", succeeded: "已成功", failed: "失败", cancelled: "已取消" } as Record<string, string>)[status] ?? status;
}

// 中栏是三段纵向堆叠：诊断报告 / 执行总账 / 实时事件流。
// 三段之间放两条可拖动的分隔条，用户想多看哪一块就往哪边拉。
const DEFAULT_WEIGHTS = [1.6, 1.1, 0.9] as const;
// 每一段的最小高度（像素）：再拉也不会把某一段压没，最差还能看到标题。
const MIN_SECTION_PX = [150, 120, 90] as const;
const KEYBOARD_STEP_PX = 32;
const LAYOUT_STORAGE_KEY = "aiops:center-layout:v1";

function sanitize(candidate: readonly unknown[]): number[] {
  const cleaned = DEFAULT_WEIGHTS.map((fallback, index) => {
    const value = candidate[index];
    return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
  });
  return cleaned;
}

/** 记住上次拖出来的布局；读不到（首次/隐私模式/坏数据）就用默认比例。 */
function initialWeights(): number[] {
  try {
    const raw = globalThis.localStorage?.getItem(LAYOUT_STORAGE_KEY);
    if (raw === null || raw === undefined) return [...DEFAULT_WEIGHTS];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length === DEFAULT_WEIGHTS.length
      ? sanitize(parsed)
      : [...DEFAULT_WEIGHTS];
  } catch {
    return [...DEFAULT_WEIGHTS];
  }
}

const bodyRef = ref<HTMLElement | null>(null);
const weights = ref<number[]>(initialWeights());

// fr 单位会在窗口尺寸变化时自动等比缩放，所以不用监听 resize。
const gridTemplateRows = computed(() => weights.value
  .map((weight) => `minmax(0, ${weight.toFixed(3)}fr)`)
  .join(" 8px "));

// 给调试和测试一个可读的布局快照，避免去解析内联样式。
const layoutSummary = computed(() => weights.value.map((weight) => weight.toFixed(2)).join("/"));

function persistWeights(): void {
  try {
    globalThis.localStorage?.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(weights.value));
  } catch {
    // 写不进去（隐私模式等）不影响本次会话里的布局。
  }
}

/**
 * 把一条分隔条的位移换算成 fr 变化量。
 *
 * 关键约束：只在这一对相邻分区之间一增一减，权重之和保持不变，
 * 所以拖上面那条不会顺带把最下面那块挤小；同时两侧都受最小高度限制。
 */
function applyDelta(index: number, deltaPx: number): void {
  const body = bodyRef.value;
  if (body === null) return;
  const totalPx = body.clientHeight;
  const start = [...weights.value];
  const totalWeight = start.reduce((sum, value) => sum + value, 0);
  if (totalPx <= 0 || totalWeight <= 0) return;
  const pxPerWeight = totalPx / totalWeight;
  const minWeights = MIN_SECTION_PX.map((px) => px / pxPerWeight);
  const lower = (minWeights[index] ?? 0) - (start[index] ?? 0);
  const upper = (start[index + 1] ?? 0) - (minWeights[index + 1] ?? 0);
  const delta = Math.min(Math.max(deltaPx / pxPerWeight, lower), Math.max(lower, upper));
  const next = [...start];
  next[index] = (start[index] ?? 0) + delta;
  next[index + 1] = (start[index + 1] ?? 0) - delta;
  weights.value = next;
}

function startDrag(index: number, event: PointerEvent): void {
  const body = bodyRef.value;
  const handle = event.currentTarget;
  if (body === null || !(handle instanceof HTMLElement)) return;
  if (typeof handle.setPointerCapture === "function") handle.setPointerCapture(event.pointerId);
  // 光标可能会跑出这条细线，所以移动监听挂在文档上而不是分隔条上。
  const target: Document = body.ownerDocument;
  let lastY = event.clientY;
  const move = (moveEvent: PointerEvent): void => {
    applyDelta(index, moveEvent.clientY - lastY);
    lastY = moveEvent.clientY;
  };
  const finish = (): void => {
    target.removeEventListener("pointermove", move);
    target.removeEventListener("pointerup", finish);
    target.removeEventListener("pointercancel", finish);
    persistWeights();
  };
  target.addEventListener("pointermove", move);
  target.addEventListener("pointerup", finish);
  target.addEventListener("pointercancel", finish);
}

function onSplitterKeydown(index: number, event: KeyboardEvent): void {
  if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
  event.preventDefault();
  applyDelta(index, event.key === "ArrowDown" ? KEYBOARD_STEP_PX : -KEYBOARD_STEP_PX);
  persistWeights();
}
</script>

<template>
  <section class="aiops-column aiops-center" aria-label="当前报告与实时 timeline">
    <header class="center-heading">
      <div><p class="eyebrow">CURRENT DIAGNOSIS</p><h2>{{ detail?.task.query || detail?.task.alerts[0]?.alertName || "选择或创建诊断" }}</h2></div>
      <div class="status-pair" aria-label="诊断与后台任务状态"><span>诊断：<strong>{{ diagnosticStatusText }} ({{ diagnosticStatus }})</strong></span><span>后台任务：<strong>{{ statusLabel(jobStatus) }} ({{ jobStatus }})</strong></span></div>
    </header>
    <div class="stream-controls">
      <span v-if="streaming" role="status"><Radio :size="14" aria-hidden="true" />正在读取持久事件</span>
      <span v-else-if="disconnected" class="stream-warning" role="alert">{{ streamError }}</span>
      <span v-else class="muted">实时流未连接</span>
      <button v-if="disconnected && detail && !['succeeded','failed','cancelled'].includes(detail.task.status)" type="button" @click="$emit('subscribe')"><RotateCw :size="14" aria-hidden="true" />手动重新订阅</button>
      <button v-if="canCancel" type="button" @click="$emit('cancel')"><Ban :size="14" aria-hidden="true" />取消后台任务</button>
    </div>

    <div ref="bodyRef" class="center-body" :style="{ gridTemplateRows }" :data-layout="layoutSummary">
      <section class="report-panel">
        <header><strong>诊断报告</strong><span v-if="detail?.report">{{ reportTrustLabel }} · {{ detail.report.generationMode === "fallback" ? "诚实 fallback" : "模型生成" }}</span></header>
        <div v-if="detail?.report" class="aiops-report-scroll">
          <div class="markdown-body" v-html="reportHtml" />
          <UserFeedbackControl
            target-type="diagnostic_report"
            :target-id="detail.report.id"
            :subject-id="null"
          />
          <section class="promotion-panel" aria-label="可信案例提升">
            <p v-if="!canPromote">只有可信证据报告且已保存“赞同”反馈后，才可提升为知识案例。</p>
            <button v-else data-action="promote-case" type="button" :disabled="promoting" @click="$emit('promote')">{{ promoting ? "正在提升" : "提升为知识案例" }}</button>
            <p v-if="promotionError" role="alert">{{ promotionError }}</p>
            <article v-for="candidate in promotionCandidates" :key="candidate.item.id" class="promotion-candidate">
              <strong>相似案例 {{ Math.round(candidate.similarityScore * 100) }}%</strong>
              <span>{{ candidate.item.summary }}</span>
              <div><button data-action="merge-case" type="button" :disabled="promoting" @click="$emit('resolvePromotion', 'merge', candidate.item.id)">合并来源</button><button data-action="create-case" type="button" :disabled="promoting" @click="$emit('resolvePromotion', 'create_new', candidate.item.id)">仍创建新案例</button></div>
            </article>
          </section>
        </div>
        <div v-else class="blank-report">最终报告将在持久任务成功后显示；失败不会伪装为成功。</div>
      </section>
      <div class="splitter" role="separator" aria-orientation="horizontal" tabindex="0" aria-label="调整诊断报告与执行总账的高度"
        data-splitter="report-ledger" @pointerdown="startDrag(0, $event)" @keydown="onSplitterKeydown(0, $event)" />
      <AiopsExecutionLedger :execution="execution" />
      <div class="splitter" role="separator" aria-orientation="horizontal" tabindex="0" aria-label="调整执行总账与实时事件流的高度"
        data-splitter="ledger-timeline" @pointerdown="startDrag(1, $event)" @keydown="onSplitterKeydown(1, $event)" />
      <section class="timeline-panel">
        <header><strong>实时事件流</strong></header>
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
.promotion-panel { margin-top: 10px; border-top: 1px solid var(--color-border); padding-top: 10px; font-size: 11px; }.promotion-panel > p { color: var(--color-text-muted); }.promotion-panel [role="alert"] { color: var(--color-danger); }.promotion-panel button { min-height: 30px; border: 1px solid var(--color-border); border-radius: 7px; padding: 5px 8px; background: white; cursor: pointer; }.promotion-candidate { display: grid; gap: 6px; margin-top: 8px; border: 1px solid var(--color-border); border-radius: 8px; padding: 9px; }.promotion-candidate > span { color: var(--color-text-muted); }.promotion-candidate > div { display: flex; gap: 6px; }
:deep(.markdown-body img) { max-width: 100%; }:deep(.markdown-body pre) { max-width: 100%; overflow: auto; }:deep(.markdown-body table) { display: block; max-width: 100%; overflow: auto; }
.splitter { position: relative; height: 8px; background: #e8efec; cursor: row-resize; touch-action: none; }.splitter::after { content: ""; position: absolute; inset: 2px 0; border-radius: 2px; transition: background .15s ease; }.splitter:hover::after,.splitter:focus-visible::after { background: #b0cfc6; }.splitter:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
</style>
