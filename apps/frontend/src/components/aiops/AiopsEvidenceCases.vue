<script setup lang="ts">
import { BookOpen, ChevronRight, ExternalLink, Link2, RefreshCw } from "lucide-vue-next";

import type {
  DiagnosticCase,
  DiagnosticDetailData,
  DiagnosticEvidenceChainData,
  UserFeedback,
} from "@super-ai/api-contracts";

defineProps<{
  detail: DiagnosticDetailData | null;
  chain: DiagnosticEvidenceChainData | null;
  cases: readonly DiagnosticCase[];
  selectedCase: DiagnosticCase | null;
  /** 展开那条案例的来源报告上，用户留下的主观反馈（评分/问题类型/评论/建议纠正）。 */
  selectedCaseFeedback: UserFeedback | null;
}>();
defineEmits<{
  selectCase: [id: string];
  closeCase: [];
  openDocument: [];
  refreshCases: [];
}>();
</script>

<template>
  <section class="aiops-column aiops-right" aria-label="证据与案例库">
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

    <section class="right-section cases-section">
      <header><span><BookOpen :size="15" aria-hidden="true" />沉淀案例</span><button type="button" aria-label="刷新案例库" @click="$emit('refreshCases')"><RefreshCw :size="13" aria-hidden="true" /></button></header>
      <div class="right-scroll">
        <p v-if="cases.length === 0" class="muted">暂无自动沉淀的诊断案例</p>
        <template v-for="item in cases" v-else :key="item.id">
          <button
            type="button"
            class="case-row"
            :class="{ 'is-selected': selectedCase?.id === item.id }"
            :aria-expanded="selectedCase?.id === item.id"
            @click="$emit('selectCase', item.id)"
          >
            <ChevronRight :size="13" class="case-row__chevron" aria-hidden="true" />
            <strong>{{ item.alertName || item.service || "诊断案例" }}</strong>
            <span>{{ item.summary }}</span>
          </button>
          <!-- 详情就地展开在这条案例下面，同一时间只可能有一条：selectedCase 只有一份。 -->
          <article v-if="selectedCase?.id === item.id" class="case-detail">
            <header class="case-detail__head">
              <h3>{{ selectedCase.alertName }}</h3>
              <button type="button" data-action="close-case" aria-label="收起案例" @click="$emit('closeCase')">收起</button>
            </header>
            <dl>
              <dt>服务</dt><dd>{{ selectedCase.service || "未标注" }}</dd>
              <dt>根因</dt><dd>{{ selectedCase.rootCause }}</dd>
              <dt>处置</dt><dd>{{ selectedCase.remediation }}</dd>
              <dt>来源任务</dt><dd>{{ selectedCase.taskId }}</dd>
              <dt>来源报告</dt><dd>{{ selectedCase.reportId }}</dd>
              <dt>证据</dt><dd>{{ selectedCase.evidenceIds.length }} 条（{{ selectedCase.evidenceIds.join("、") || "空" }}）</dd>
            </dl>
            <!-- 用户在中间栏报告下方填的反馈存在来源报告上，这里把主观内容一并摊开，
                 否则"点了保存但不知道存到哪去了"。 -->
            <section class="case-feedback" aria-label="来源报告的用户反馈">
              <strong>用户反馈</strong>
              <template v-if="selectedCaseFeedback">
                <dl>
                  <dt>评分</dt><dd>{{ selectedCaseFeedback.rating === "positive" ? "赞同" : "反对" }}</dd>
                  <dt>问题类型</dt><dd>{{ selectedCaseFeedback.reason ?? "未选择" }}</dd>
                  <dt>评论</dt><dd>{{ selectedCaseFeedback.comment || "（空）" }}</dd>
                  <dt>建议纠正</dt><dd>{{ selectedCaseFeedback.correction || "（空）" }}</dd>
                </dl>
                <small>保存于 {{ selectedCaseFeedback.updatedAt }}，可在中间栏报告下方修改。</small>
              </template>
              <small v-else>这条案例的来源报告还没有反馈内容。</small>
            </section>
            <button type="button" @click="$emit('openDocument')"><ExternalLink :size="13" aria-hidden="true" />打开 owner 知识文档</button>
          </article>
        </template>
      </div>
    </section>
  </section>
</template>

<style scoped>
.aiops-column { min-width: 0; min-height: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); overflow: hidden; }.aiops-right { display: grid; grid-template-rows: minmax(220px, 1.15fr) minmax(200px, 1fr); }.right-section { min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); border-bottom: 1px solid var(--color-border); }.right-section > header { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; }.right-section header > span { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; }.right-section header small { color: var(--color-text-muted); }.right-section header button { width: 28px; height: 28px; border: 1px solid var(--color-border); border-radius: 7px; display: grid; place-items: center; background: white; cursor: pointer; }.right-scroll { min-height: 0; padding: 0 10px 10px; overflow: auto; }.muted { margin: 8px 2px; color: var(--color-text-muted); font-size: 11px; }.evidence-card,.execution-card,.case-detail,.step-feedback-card { border: 1px solid var(--color-border); border-radius: 8px; padding: 9px; margin-bottom: 7px; }.evidence-card > div,.execution-card summary { display: flex; justify-content: space-between; gap: 8px; }.evidence-card span,.evidence-card small,.execution-card span { color: var(--color-text-muted); font-size: 10px; }.evidence-card p,.execution-card p,.provenance-links p { margin: 5px 0; color: var(--color-text-muted); font-size: 11px; line-height: 1.45; }.provenance-links { padding: 8px; font-size: 11px; }.execution-card summary { cursor: pointer; }.execution-detail { white-space: pre-line; }.case-row { width: 100%; border: 1px solid transparent; border-radius: 7px; display: grid; gap: 3px; padding: 8px; text-align: left; background: transparent; cursor: pointer; }.case-row span { overflow: hidden; color: var(--color-text-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.case-row:hover,.case-row.is-selected { border-color: #c9dcd7; background: var(--color-accent-soft); }.case-detail h3 { margin: 0 0 7px; font-size: 13px; }.case-detail dl { display: grid; grid-template-columns: 38px 1fr; gap: 4px 8px; margin: 0; font-size: 10px; }.case-detail dt { color: var(--color-text-muted); }.case-detail dd { margin: 0; line-height: 1.45; }.case-detail button { margin-top: 9px; border: 1px solid var(--color-border); border-radius: 7px; display: inline-flex; align-items: center; gap: 5px; padding: 6px 8px; background: white; cursor: pointer; font-size: 10px; }
.case-row { grid-template-columns: 15px 1fr; align-items: center; gap: 3px 4px; }.case-row > strong { grid-column: 2; }.case-row > span { grid-column: 2; }.case-row__chevron { grid-row: 1 / span 2; color: var(--color-text-muted); transition: transform .15s ease; }.case-row[aria-expanded="true"] .case-row__chevron { transform: rotate(90deg); }.case-detail__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }.case-detail__head button { margin-top: 0; }.case-detail dd { overflow-wrap: anywhere; }.case-feedback { display: grid; gap: 5px; margin-top: 9px; padding: 8px; border: 1px solid var(--color-border); border-radius: 7px; background: #fbfdfc; }.case-feedback > strong { font-size: 11px; }.case-feedback small { color: var(--color-text-muted); font-size: 9px; }
</style>
