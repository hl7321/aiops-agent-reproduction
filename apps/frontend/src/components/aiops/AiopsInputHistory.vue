<script setup lang="ts">
import { Bell, History, Play, RefreshCw } from "lucide-vue-next";
import { computed, ref } from "vue";

import type { ActiveAlert, DiagnosticTask } from "@super-ai/api-contracts";

import { diagnosticStatusLabel as statusLabel } from "../../aiops/status";
const props = defineProps<{
  alerts: readonly ActiveAlert[];
  history: readonly DiagnosticTask[];
  selectedTaskId: string | null;
  alertError: string | null;
  creating: boolean;
}>();
const emit = defineEmits<{
  create: [query: string, alert: ActiveAlert | null];
  refreshAlerts: [];
  selectTask: [id: string];
}>();

const query = ref("");
const selectedAlertKey = ref<string | null>(null);
const selectedAlert = computed(() => props.alerts.find(
  (alert) => alertKey(alert) === selectedAlertKey.value,
) ?? null);

function selectAlert(alert: ActiveAlert): void {
  selectedAlertKey.value = alertKey(alert);
  if (!query.value.trim()) {
    query.value = `排查 ${alert.service ? `${alert.service} 的 ` : ""}${alert.alertName}`;
  }
}

function create(): void {
  emit("create", query.value, selectedAlert.value);
}

function alertKey(alert: ActiveAlert): string {
  return `${alert.source.name}:${alert.alertName}:${alert.startsAt}`;
}

</script>

<template>
  <section class="aiops-column aiops-left" aria-label="诊断输入、活跃告警和历史">
    <header class="column-heading"><div><p class="eyebrow">DIAGNOSE</p><h2>诊断输入</h2></div></header>
    <form class="diagnosis-form" @submit.prevent="create">
      <label for="diagnosis-query">手工问题</label>
      <textarea id="diagnosis-query" v-model="query" rows="4" maxlength="4000" placeholder="例如：排查 checkout 延迟升高" />
      <p>可只输入问题，也可选择一条真实告警作为诊断快照；当前请求没有独立 context 字段。</p>
      <button class="button button--primary" type="submit" :disabled="creating || (!query.trim() && selectedAlert === null)">
        <Play :size="15" aria-hidden="true" />{{ creating ? "正在创建" : "创建持久诊断" }}
      </button>
    </form>

    <section class="left-section alerts-section">
      <header><span><Bell :size="16" aria-hidden="true" />活跃告警</span><button type="button" aria-label="刷新真实告警" @click="emit('refreshAlerts')"><RefreshCw :size="14" aria-hidden="true" /></button></header>
      <p v-if="alertError" class="inline-error" role="alert">{{ alertError }}</p>
      <p v-else-if="alerts.length === 0" class="muted">当前没有真实活跃告警</p>
      <div v-else class="bounded-list" aria-label="真实活跃告警列表">
        <button
          v-for="alert in alerts" :key="alertKey(alert)" type="button" class="alert-row"
          :class="{ 'is-selected': alertKey(alert) === selectedAlertKey }" @click="selectAlert(alert)"
        >
          <strong>{{ alert.alertName }}</strong><span>{{ alert.service ?? "未知服务" }} · {{ alert.severity ?? "未标级别" }}</span><small>{{ alert.source.name }} · {{ alert.status }}</small>
        </button>
      </div>
    </section>

    <section class="left-section history-section">
      <header><span><History :size="16" aria-hidden="true" />诊断历史</span></header>
      <p v-if="history.length === 0" class="muted">暂无持久诊断历史</p>
      <div v-else class="bounded-list" aria-label="持久诊断历史">
        <button
          v-for="task in history" :key="task.id" type="button" class="history-row"
          :class="{ 'is-selected': task.id === selectedTaskId }" @click="emit('selectTask', task.id)"
        >
          <strong>{{ task.query || task.alerts[0]?.alertName || "告警诊断" }}</strong>
          <span>{{ statusLabel(task) }} · {{ task.updatedAt }}</span>
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.aiops-column { min-width: 0; min-height: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); overflow: hidden; }
.aiops-left { display: grid; grid-template-rows: auto auto minmax(145px, .8fr) minmax(160px, 1fr); }
.column-heading,.left-section > header { display: flex; align-items: center; justify-content: space-between; }.column-heading { padding: 14px 16px 10px; }.column-heading h2 { margin: 2px 0 0; font-size: 18px; }
.diagnosis-form { display: grid; gap: 8px; padding: 0 16px 14px; border-bottom: 1px solid var(--color-border); }.diagnosis-form label,.left-section header span { font-size: 12px; font-weight: 700; }.diagnosis-form textarea { resize: none; min-height: 82px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 9px; font: inherit; }.diagnosis-form p { margin: 0; color: var(--color-text-muted); font-size: 11px; line-height: 1.5; }.diagnosis-form button { justify-self: stretch; justify-content: center; }
.left-section { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); border-bottom: 1px solid var(--color-border); }.left-section > header { padding: 10px 14px; }.left-section header span { display: flex; align-items: center; gap: 6px; }.left-section header button { width: 29px; height: 29px; border: 1px solid var(--color-border); border-radius: 7px; display: grid; place-items: center; background: white; cursor: pointer; }.bounded-list { min-height: 0; padding: 0 10px 10px; overflow: auto; }.alert-row,.history-row { width: 100%; min-width: 0; border: 1px solid transparent; border-radius: 8px; display: grid; gap: 3px; padding: 9px; text-align: left; background: transparent; cursor: pointer; }.alert-row:hover,.history-row:hover,.is-selected { border-color: #c9dcd7; background: var(--color-accent-soft); }.alert-row span,.history-row span,.alert-row small { overflow: hidden; color: var(--color-text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.inline-error,.muted { margin: 0; padding: 8px 14px; font-size: 11px; }.inline-error { color: var(--color-danger); }.muted { color: var(--color-text-muted); }
</style>
