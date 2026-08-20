<script setup lang="ts">
import { ChevronDown, ChevronRight, RefreshCw, RotateCcw, Trash2 } from "lucide-vue-next";

import type { ChunkPreviewData, DocumentIndexTask, KnowledgeDocument } from "@super-ai/api-contracts";

import AsyncStatusBadge from "../components/states/AsyncStatusBadge.vue";
import KnowledgeDocumentDetail from "./KnowledgeDocumentDetail.vue";

defineProps<{
  documents: readonly KnowledgeDocument[];
  tasksByDocument: Readonly<Record<string, DocumentIndexTask>>;
  selectedDocument: KnowledgeDocument | null;
  previewsByDocument: Readonly<Record<string, ChunkPreviewData>>;
}>();
const emit = defineEmits<{
  select: [documentId: string];
  delete: [documentId: string];
  retry: [documentId: string];
  rebuild: [documentId: string];
}>();

const statusText: Record<KnowledgeDocument["indexStatus"], string> = {
  pending: "等待索引",
  running: "正在索引",
  succeeded: "索引成功",
  failed: "索引失败",
  cancelled: "索引已取消",
};
const badgeStatus: Record<KnowledgeDocument["indexStatus"], "idle" | "loading" | "success" | "error"> = {
  pending: "loading",
  running: "loading",
  succeeded: "success",
  failed: "error",
  cancelled: "idle",
};

</script>

<template>
  <section class="knowledge-document-list" aria-label="知识文档列表">
    <div class="knowledge-table-scroll" tabindex="0" aria-label="文档表格，可纵向和横向滚动">
      <table>
        <thead>
          <tr><th>文档</th><th>类型 / 大小</th><th>切分策略</th><th>索引状态</th><th>上传时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <template v-for="document in documents" :key="document.id">
            <tr>
              <td class="document-name-cell">
                <button
                  class="expand-button"
                  type="button"
                  :aria-expanded="selectedDocument?.id === document.id"
                  :aria-label="`${selectedDocument?.id === document.id ? '收起' : '展开'} ${document.filename} 详情`"
                  @click="emit('select', document.id)"
                >
                  <ChevronDown v-if="selectedDocument?.id === document.id" :size="16" aria-hidden="true" />
                  <ChevronRight v-else :size="16" aria-hidden="true" />
                  <span>{{ document.filename }}</span>
                </button>
                <small>{{ document.id }}</small>
              </td>
              <td>{{ document.mimeType }}<br><small>{{ Math.ceil(document.sizeBytes / 1024) }} KiB</small></td>
              <td>{{ document.chunkingConfig.strategy }}</td>
              <td><AsyncStatusBadge :status="badgeStatus[document.indexStatus]" :label="statusText[document.indexStatus]" /></td>
              <td>{{ new Date(document.uploadedAt).toLocaleString('zh-CN') }}</td>
              <td>
                <div class="row-actions">
                  <button
                    v-if="tasksByDocument[document.id]?.status !== 'pending' && tasksByDocument[document.id]?.status !== 'running'"
                    class="icon-button"
                    type="button"
                    :aria-label="`重新索引 ${document.filename}`"
                    @click="emit('rebuild', document.id)"
                  ><RefreshCw :size="16" aria-hidden="true" /></button>
                  <button
                    v-if="tasksByDocument[document.id]?.status === 'failed' || tasksByDocument[document.id]?.status === 'cancelled'"
                    class="icon-button"
                    type="button"
                    :aria-label="`重试 ${document.filename} 索引`"
                    @click="emit('retry', document.id)"
                  ><RotateCcw :size="16" aria-hidden="true" /></button>
                  <button class="icon-button" type="button" :aria-label="`删除 ${document.filename}`" @click="emit('delete', document.id)">
                    <Trash2 :size="16" aria-hidden="true" />
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="selectedDocument?.id === document.id" class="detail-row">
              <td colspan="6">
                <KnowledgeDocumentDetail
                  :document="selectedDocument"
                  :preview="previewsByDocument[document.id]"
                  :task="tasksByDocument[document.id]"
                  @retry="emit('retry', $event)"
                />
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.knowledge-document-list { min-width: 0; min-height: 0; height: 100%; border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; background: var(--color-surface); }
.knowledge-table-scroll { width: 100%; height: 100%; overflow: auto; }
.knowledge-table-scroll > table { width: 100%; min-width: 980px; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--color-border); padding: 12px 14px; text-align: left; vertical-align: middle; font-size: 12px; }
th { position: sticky; top: 0; z-index: 1; color: var(--color-text-muted); background: var(--color-surface-subtle); font-size: 11px; letter-spacing: .04em; }
tbody tr:last-child td { border-bottom: 0; }
.document-name-cell { max-width: 300px; }
.document-name-cell small, td small { color: var(--color-text-muted); }
.expand-button { max-width: 100%; border: 0; display: flex; align-items: center; gap: 7px; padding: 0; background: transparent; cursor: pointer; font-weight: 700; }
.expand-button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-actions { display: flex; gap: 6px; }
.row-actions .icon-button { width: 34px; height: 34px; }
.detail-row > td { padding: 0; }
</style>
