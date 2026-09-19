<script setup lang="ts">
import { Clock, Filter } from "lucide-vue-next";
import { computed, onBeforeUnmount, ref } from "vue";

import type { DiagnosticExecutionResult } from "@super-ai/api-contracts";

const props = defineProps<{ execution: DiagnosticExecutionResult | null }>();

/** 毫秒转成好读的时长；没有数据时如实显示未知，不编造 0。 */
function formatDuration(value: number | null): string {
  if (value === null) return "—";
  if (value < 1000) return `${value} 毫秒`;
  return `${(value / 1000).toFixed(1)} 秒`;
}

// 正在进行的步骤还没写完成时间，后端返回的 durationMs 是 null。
// 这里用一个本地秒表把它显示成"已进行 X 秒"，让运行中也有持续变化的时间。
const nowMs = ref(Date.now());
const ticker = setInterval(() => { nowMs.value = Date.now(); }, 1000);
onBeforeUnmount(() => { clearInterval(ticker); });

function formatElapsed(startedAt: string | null): string | null {
  if (startedAt === null) return null;
  const started = Date.parse(startedAt);
  if (Number.isNaN(started)) return null;
  const elapsed = Math.max(0, nowMs.value - started);
  return formatDuration(elapsed);
}

/** 有完成时间就用后端给的权威耗时，否则用本地秒表显示进行中。 */
function stepDuration(status: string, durationMs: number | null, startedAt: string | null): string {
  if (durationMs !== null) return formatDuration(durationMs);
  if (status === "running" || status === "pending") {
    const elapsed = formatElapsed(startedAt);
    if (elapsed !== null) return `已进行 ${elapsed}`;
  }
  return "—";
}

// 总耗时：任务跑完用后端算好的权威值；还在跑就用本地秒表从"真正的开始时刻"往上走。
// 任务刚受理、还没开始执行时用创建时间兜底，避免整块显示成"—"让人以为没在动。
const totalDuration = computed(() => {
  const execution = props.execution;
  if (execution === null) return "—";
  if (execution.durationMs !== null) return formatDuration(execution.durationMs);
  const elapsed = formatElapsed(execution.startedAt ?? execution.createdAt);
  return elapsed === null ? "—" : `已进行 ${elapsed}`;
});

const runningStage = computed(() => {
  const stages = props.execution?.stages ?? [];
  // 阶段的开始/结束时间由后端按真实时间戳切出来，这里只找"已经起步但还没收尾"的那一段。
  // 不能只看最后一段：规划期间真正在跑的是"规划"，最后一段"报告"还没开始。
  const active = stages.find((stage) => stage.startedAt !== null && stage.durationMs === null);
  return active?.name ?? null;
});

function statusLabel(status: string): string {
  return ({
    pending: "等待中",
    running: "进行中",
    succeeded: "成功",
    failed: "失败",
    cancelled: "已取消",
  } as Record<string, string>)[status] ?? status;
}

const evidenceSummary = (): string => {
  const entries = Object.entries(props.execution?.evidenceByKind ?? {});
  if (entries.length === 0) return "本次没有产生证据";
  return entries.map(([kind, count]) => `${kind} × ${count}`).join(" · ");
};
</script>

<template>
  <section class="ledger" aria-label="执行总账">
    <header class="ledger-head">
      <span><Clock :size="14" aria-hidden="true" />执行总账</span>
      <small>
        <template v-if="runningStage">进行中：{{ runningStage }} · </template>
        总耗时 <strong>{{ totalDuration }}</strong>
      </small>
    </header>

    <p v-if="!execution" class="ledger-muted">尚无执行记录。</p>
    <div v-else class="ledger-body">
      <!-- 阶段耗时：受理 → 规划 → 执行 → 报告，来自真实时间戳 -->
      <ol class="stage-strip" aria-label="阶段耗时">
        <li v-for="stage in execution.stages" :key="stage.name">
          <span>{{ stage.name }}</span>
          <strong>
            {{ stage.durationMs === null && stage.startedAt !== null
              ? `进行中 ${formatElapsed(stage.startedAt) ?? ""}`
              : formatDuration(stage.durationMs) }}
          </strong>
        </li>
      </ol>

      <!-- 逐步对账：计划意图与真实执行结果同列一行 -->
      <article v-for="step in execution.plan" :key="step.position" class="ledger-step" :data-status="step.status">
        <div class="ledger-step__head">
          <strong>步骤 {{ step.position + 1 }}：{{ step.toolName }}</strong>
          <span>{{ statusLabel(step.status) }}</span>
          <time>{{ stepDuration(step.status, step.durationMs, step.startedAt) }}</time>
        </div>
        <p class="ledger-step__purpose">{{ step.purpose }}</p>
        <ul class="attempt-list">
          <li v-for="attempt in step.attempts" :key="attempt.attempt">
            <span class="attempt-head">
              第 {{ attempt.attempt }} 次尝试 · {{ statusLabel(attempt.status) }} ·
              {{ stepDuration(attempt.status, attempt.durationMs, attempt.startedAt) }}
              <em v-if="attempt.failureClass">（{{ attempt.failureClass }}）</em>
            </span>
            <span class="attempt-body">{{ attempt.resultSummary ?? attempt.errorMessage ?? "无摘要" }}</span>
            <small v-if="attempt.argumentKeys.length">参数键：{{ attempt.argumentKeys.join("、") }}</small>
          </li>
          <li v-if="step.attempts.length === 0" class="attempt-empty">这一步尚未执行</li>
        </ul>
        <p v-if="step.producedEvidence.length" class="ledger-step__produced">
          产出 {{ step.producedEvidence.length }} 条证据：{{ step.producedEvidence.map((item) => item.kind).join("、") }}
        </p>
      </article>

      <p class="ledger-evidence">
        <Filter :size="13" aria-hidden="true" />证据统计：{{ evidenceSummary() }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.ledger { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); border-bottom: 1px solid var(--color-border); }
.ledger-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 12px; }
.ledger-head > span { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; }
.ledger-head small { color: var(--color-text-muted); font-size: 10px; }
.ledger-head strong { color: var(--color-text); font-size: 11px; }
.ledger-muted { margin: 0; padding: 0 12px 12px; color: var(--color-text-muted); font-size: 11px; }
.ledger-body { min-height: 0; padding: 0 12px 10px; overflow: auto; }
.stage-strip { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 9px; padding: 0; list-style: none; }
.stage-strip li { display: grid; gap: 1px; min-width: 68px; border: 1px solid var(--color-border); border-radius: 7px; padding: 5px 7px; background: #fbfdfc; }
.stage-strip span { color: var(--color-text-muted); font-size: 10px; }
.stage-strip strong { font-size: 11px; }
.ledger-step { border: 1px solid var(--color-border); border-radius: 8px; padding: 8px 9px; margin-bottom: 7px; }
.ledger-step[data-status="failed"] { border-color: #e6c9c4; background: #fdf7f6; }
.ledger-step__head { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.ledger-step__head strong { font-size: 11px; }
.ledger-step__head span { color: var(--color-text-muted); font-size: 10px; }
.ledger-step__head time { color: var(--color-text-muted); font-size: 10px; font-variant-numeric: tabular-nums; }
.ledger-step__purpose { margin: 4px 0 6px; color: var(--color-text-muted); font-size: 11px; line-height: 1.45; }
.attempt-list { display: grid; gap: 5px; margin: 0; padding: 0; list-style: none; }
.attempt-list li { display: grid; gap: 2px; border-left: 2px solid #dbe7e3; padding-left: 8px; }
.attempt-head { font-size: 10px; font-weight: 700; }
.attempt-head em { color: #b4553c; font-style: normal; font-weight: 600; }
.attempt-body { color: var(--color-text-muted); font-size: 10px; line-height: 1.45; }
.attempt-list small { color: var(--color-text-muted); font-size: 9px; }
.attempt-empty { color: var(--color-text-muted); font-size: 10px; }
.ledger-step__produced { margin: 6px 0 0; color: #2f6b5f; font-size: 10px; }
.ledger-evidence { display: flex; align-items: center; gap: 6px; margin: 2px 0 0; color: var(--color-text-muted); font-size: 10px; }
</style>
