<script setup lang="ts">
import { computed } from "vue";

import type { ChatReference, JsonValue } from "@super-ai/api-contracts";

const props = defineProps<{ references: readonly ChatReference[] }>();

const visibleReferences = computed(() => [...props.references]
  .sort((left, right) => left.rerankRank - right.rerankRank
    || right.rerankScore - left.rerankScore
    || left.chunkId.localeCompare(right.chunkId))
  .slice(0, 5));

function rank(value: number | null): string {
  return value === null ? "未命中" : `#${value}`;
}

function score(value: number | null): string {
  return value === null ? "未命中" : value.toFixed(4);
}

function displayMetadata(value: JsonValue): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
</script>

<template>
  <section v-if="visibleReferences.length > 0" class="chat-citations" aria-label="本轮引用">
    <h4>引用来源</h4>
    <article v-for="reference in visibleReferences" :key="reference.chunkId" class="citation-card">
      <div class="citation-card__header">
        <strong>{{ reference.source }}</strong>
        <span>重排 #{{ reference.rerankRank }} · {{ reference.rerankScore.toFixed(4) }}</span>
      </div>
      <p>{{ reference.excerpt }}</p>
      <div class="citation-card__identity">
        <span>文档 {{ reference.documentId }}</span>
        <span>知识库 {{ reference.knowledgeBaseId }}</span>
      </div>
      <details>
        <summary>查看检索轨迹与元数据</summary>
        <dl class="citation-trace">
          <div><dt>向量排名</dt><dd>{{ rank(reference.vectorRank) }}</dd></div>
          <div><dt>向量分数</dt><dd>{{ score(reference.vectorScore) }}</dd></div>
          <div><dt>BM25 排名</dt><dd>{{ rank(reference.bm25Rank) }}</dd></div>
          <div><dt>BM25 分数</dt><dd>{{ score(reference.bm25Score) }}</dd></div>
          <div><dt>RRF 分数</dt><dd>{{ reference.rrfScore.toFixed(4) }}</dd></div>
          <div><dt>重排排名</dt><dd>#{{ reference.rerankRank }}</dd></div>
          <div><dt>重排分数</dt><dd>{{ reference.rerankScore.toFixed(4) }}</dd></div>
        </dl>
        <dl class="citation-metadata">
          <div v-for="(value, key) in reference.metadata" :key="key">
            <dt>{{ key }}</dt><dd>{{ displayMetadata(value) }}</dd>
          </div>
        </dl>
        <RouterLink :to="{ path: '/knowledge', query: {
          knowledgeBaseId: reference.knowledgeBaseId,
          documentId: reference.documentId,
        } }">前往所属文档</RouterLink>
      </details>
    </article>
  </section>
</template>
