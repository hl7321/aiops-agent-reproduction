<script setup lang="ts">
import type { ChunkPreviewData, DocumentIndexTask, KnowledgeDocument } from "@super-ai/api-contracts";

const props = defineProps<{
  document: KnowledgeDocument;
  preview: ChunkPreviewData | undefined;
  task: DocumentIndexTask | undefined;
}>();
const emit = defineEmits<{ retry: [documentId: string] }>();

function displayMetadata(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
</script>

<template>
  <section class="knowledge-document-detail" :aria-label="`${document.filename} 详情`">
    <div class="detail-column">
      <h3>文档 metadata</h3>
      <div class="metadata-scroll" tabindex="0" aria-label="文档 metadata，可滚动">
        <table>
          <tbody>
            <tr><th>文档 ID</th><td>{{ document.id }}</td></tr>
            <tr><th>知识库 ID</th><td>{{ document.knowledgeBaseId }}</td></tr>
            <tr><th>SHA-256</th><td>{{ document.sha256 }}</td></tr>
            <tr><th>MIME</th><td>{{ document.mimeType }}</td></tr>
            <tr><th>切分策略</th><td>{{ document.chunkingConfig.strategy }}</td></tr>
          </tbody>
        </table>
      </div>
      <div v-if="task?.failureReason" class="task-failure" role="alert">
        <strong>索引失败原因</strong>
        <span>{{ task.failureReason }}</span>
        <button
          v-if="task.status === 'failed' || task.status === 'cancelled'"
          class="text-button"
          type="button"
          :aria-label="`重试 ${document.filename} 索引`"
          @click="emit('retry', document.id)"
        >重试索引</button>
      </div>
    </div>
    <div class="detail-column">
      <h3>实际切分预览 <span v-if="preview">共 {{ preview.totalChunks }} 段</span></h3>
      <div class="preview-scroll" tabindex="0" aria-label="实际切分预览，可滚动">
        <p v-if="!preview" role="status">正在读取实际切分结果</p>
        <article v-for="item in preview?.items ?? []" :key="item.index" class="preview-chunk">
          <strong>第 {{ item.index + 1 }} 段</strong>
          <p>{{ item.excerpt }}</p>
          <dl>
            <template v-for="(value, key) in item.metadata" :key="key">
              <dt>{{ key }}</dt><dd>{{ displayMetadata(value) }}</dd>
            </template>
          </dl>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.knowledge-document-detail { min-width: 0; display: grid; grid-template-columns: minmax(300px, .8fr) minmax(420px, 1.2fr); gap: var(--space-4); padding: var(--space-4); background: var(--color-surface-subtle); }
.detail-column { min-width: 0; }
.detail-column h3 { margin: 0 0 10px; font-size: 13px; }
.detail-column h3 span { color: var(--color-text-muted); font-weight: 500; }
.metadata-scroll, .preview-scroll { max-height: 220px; overflow: auto; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); }
.metadata-scroll table { min-width: 520px; border-collapse: collapse; font-size: 12px; }
.metadata-scroll th, .metadata-scroll td { border-bottom: 1px solid var(--color-border); padding: 9px 11px; text-align: left; overflow-wrap: anywhere; }
.metadata-scroll th { width: 110px; color: var(--color-text-muted); }
.preview-scroll { display: grid; gap: 10px; padding: 10px; }
.preview-scroll > p { margin: 16px; color: var(--color-text-muted); }
.preview-chunk { border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 12px; }
.preview-chunk > p { margin: 8px 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
.preview-chunk dl { margin: 0; display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px 10px; color: var(--color-text-muted); font-size: 11px; }
.preview-chunk dt { font-weight: 700; }
.preview-chunk dd { margin: 0; overflow-wrap: anywhere; }
.task-failure { margin-top: 10px; border: 1px solid #ecc4c4; border-radius: var(--radius-sm); display: grid; gap: 6px; padding: 10px; color: var(--color-danger); background: var(--color-danger-soft); font-size: 12px; }
.text-button { justify-self: start; border: 0; padding: 0; color: var(--color-accent); background: transparent; font-weight: 700; cursor: pointer; }
</style>
