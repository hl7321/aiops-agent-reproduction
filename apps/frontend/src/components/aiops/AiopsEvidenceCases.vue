<script setup lang="ts">
import { BookOpen, ExternalLink, Link2, RefreshCw, Wrench } from "lucide-vue-next";

import type {
  DiagnosticCase,
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
} from "@super-ai/api-contracts";

import type { AiopsTimelineItem } from "../../aiops/timeline";

defineProps<{
  detail: DiagnosticDetailData | null;
  chain: DiagnosticEvidenceChainData | null;
  executionChain: readonly AiopsTimelineItem[];
  cases: readonly DiagnosticCase[];
  selectedCase: DiagnosticCase | null;
}>();
defineEmits<{ selectCase: [id: string]; openDocument: []; refreshCases: [] }>();
</script>

<template>
  <section class="aiops-column aiops-right" aria-label="证据、执行链和案例库">
    <section class="right-section evidence-section">
      <header><span><Link2 :size="15" aria-hidden="true" />证据与 Provenance</span><small>{{ chain?.evidence.length ?? 0 }} 条</small></header>
      <div class="right-scroll">
        <p v-if="!chain?.evidence.length" class="muted">尚无持久证据</p>
        <article v-for="evidence in chain?.evidence" v-else :key="evidence.id" class="evidence-card">
          <div><strong>{{ evidence.title }}</strong><span>{{ evidence.kind }}</span></div><p>{{ evidence.summary }}</p><small>{{ evidence.source }} · {{ evidence.id }}</small>
        </article>
        <div v-if="chain?.reportEvidenceLinks.length" class="provenance-links"><strong>报告引用</strong><p v-for="link in chain.reportEvidenceLinks" :key="link.id">{{ link.section }} → {{ link.evidenceId }}</p></div>
      </div>
    </section>

    <section class="right-section execution-section">
      <header><span><Wrench :size="15" aria-hidden="true" />执行链</span><small>{{ detail?.steps.length ?? 0 }} 步</small></header>
      <div class="right-scroll">
        <p v-if="executionChain.length === 0" class="muted">尚无持久步骤或工具审计</p>
        <details v-for="entry in executionChain" v-else :key="entry.key" class="execution-card">
          <summary><strong>{{ entry.title }}</strong><span>{{ entry.status }}</span></summary><p>{{ entry.summary }}</p><p v-if="entry.detail">{{ entry.detail }}</p>
        </details>
      </div>
    </section>

    <section class="right-section cases-section">
      <header><span><BookOpen :size="15" aria-hidden="true" />案例库</span><button type="button" aria-label="刷新案例库" @click="$emit('refreshCases')"><RefreshCw :size="13" aria-hidden="true" /></button></header>
      <div class="right-scroll">
        <p v-if="cases.length === 0" class="muted">暂无自动沉淀的诊断案例</p>
        <button v-for="item in cases" v-else :key="item.id" type="button" class="case-row" :class="{ 'is-selected': selectedCase?.id === item.id }" @click="$emit('selectCase', item.id)"><strong>{{ item.alertName || item.service || "诊断案例" }}</strong><span>{{ item.summary }}</span></button>
        <article v-if="selectedCase" class="case-detail">
          <h3>{{ selectedCase.alertName }}</h3><dl><dt>服务</dt><dd>{{ selectedCase.service || "未标注" }}</dd><dt>根因</dt><dd>{{ selectedCase.rootCause }}</dd><dt>处置</dt><dd>{{ selectedCase.remediation }}</dd><dt>来源任务</dt><dd>{{ selectedCase.taskId }}</dd><dt>来源报告</dt><dd>{{ selectedCase.reportId }}</dd><dt>证据</dt><dd>{{ selectedCase.evidenceIds.length }} 条（{{ selectedCase.evidenceIds.join("、") || "空" }}）</dd></dl>
          <button type="button" @click="$emit('openDocument')"><ExternalLink :size="13" aria-hidden="true" />打开 owner 知识文档</button>
        </article>
      </div>
    </section>
  </section>
</template>

<style scoped>
.aiops-column { min-width: 0; min-height: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); overflow: hidden; }.aiops-right { display: grid; grid-template-rows: minmax(180px, 1fr) minmax(150px, .85fr) minmax(180px, 1fr); }.right-section { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); border-bottom: 1px solid var(--color-border); }.right-section > header { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; }.right-section header > span { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; }.right-section header small { color: var(--color-text-muted); }.right-section header button { width: 28px; height: 28px; border: 1px solid var(--color-border); border-radius: 7px; display: grid; place-items: center; background: white; cursor: pointer; }.right-scroll { min-height: 0; padding: 0 10px 10px; overflow: auto; }.muted { margin: 8px 2px; color: var(--color-text-muted); font-size: 11px; }.evidence-card,.execution-card,.case-detail { border: 1px solid var(--color-border); border-radius: 8px; padding: 9px; margin-bottom: 7px; }.evidence-card > div,.execution-card summary { display: flex; justify-content: space-between; gap: 8px; }.evidence-card span,.evidence-card small,.execution-card span { color: var(--color-text-muted); font-size: 10px; }.evidence-card p,.execution-card p,.provenance-links p { margin: 5px 0; color: var(--color-text-muted); font-size: 11px; line-height: 1.45; }.provenance-links { padding: 8px; font-size: 11px; }.execution-card summary { cursor: pointer; }.case-row { width: 100%; border: 1px solid transparent; border-radius: 7px; display: grid; gap: 3px; padding: 8px; text-align: left; background: transparent; cursor: pointer; }.case-row span { overflow: hidden; color: var(--color-text-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.case-row:hover,.case-row.is-selected { border-color: #c9dcd7; background: var(--color-accent-soft); }.case-detail h3 { margin: 0 0 7px; font-size: 13px; }.case-detail dl { display: grid; grid-template-columns: 38px 1fr; gap: 4px 8px; margin: 0; font-size: 10px; }.case-detail dt { color: var(--color-text-muted); }.case-detail dd { margin: 0; line-height: 1.45; }.case-detail button { margin-top: 9px; border: 1px solid var(--color-border); border-radius: 7px; display: inline-flex; align-items: center; gap: 5px; padding: 6px 8px; background: white; cursor: pointer; font-size: 10px; }
</style>
