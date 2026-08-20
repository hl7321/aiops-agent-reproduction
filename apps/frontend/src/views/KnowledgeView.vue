<script setup lang="ts">
import { Database } from "lucide-vue-next";
import { onBeforeUnmount, onMounted } from "vue";

import type { ChunkingConfig } from "@super-ai/api-contracts";

import AppEmptyState from "../components/states/AppEmptyState.vue";
import AppErrorState from "../components/states/AppErrorState.vue";
import AppLoadingState from "../components/states/AppLoadingState.vue";
import KnowledgeDocumentTable from "../knowledge/KnowledgeDocumentTable.vue";
import KnowledgeUploadPanel from "../knowledge/KnowledgeUploadPanel.vue";
import { useFeedbackStore } from "../stores/feedback";
import { useKnowledgeStore } from "../stores/knowledge";

const store = useKnowledgeStore();
const feedback = useFeedbackStore();

onMounted(async () => {
  try {
    await store.initialize();
  } catch {
    // Store exposes the safe message through errorMessage.
  }
});
onBeforeUnmount(() => store.reset());

async function upload(file: File, config: ChunkingConfig): Promise<void> {
  try {
    await store.upload(file, config);
    if (store.overwriteConfirmation === null) feedback.show("success", "文档已上传，索引任务已创建");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "上传失败");
  }
}

async function selectDocument(documentId: string): Promise<void> {
  if (store.selectedDocument?.id === documentId) {
    store.selectedDocument = null;
    return;
  }
  try {
    await Promise.all([store.loadDocument(documentId), store.loadPreview(documentId)]);
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "读取文档详情失败");
  }
}

async function retry(documentId: string): Promise<void> {
  try {
    await store.retryTask(documentId);
    feedback.show("info", "已创建新的索引重试任务");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "重试失败");
  }
}

async function rebuild(documentId: string): Promise<void> {
  try {
    await store.rebuildDocument(documentId);
    feedback.show("info", "已创建文档重建任务");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "重建失败");
  }
}

async function confirmOverwrite(): Promise<void> {
  try {
    await store.confirmOverwrite();
    feedback.show("success", "已覆盖旧文档并创建索引任务");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "覆盖失败");
  }
}

async function confirmDelete(): Promise<void> {
  try {
    await store.confirmDelete();
    feedback.show("success", "文档已删除");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "删除失败");
  }
}
</script>

<template>
  <div class="knowledge-workspace" data-route-canvas="knowledge">
    <header class="knowledge-heading">
      <div class="knowledge-heading__icon"><Database :size="22" aria-hidden="true" /></div>
      <div>
        <p class="eyebrow">KNOWLEDGE</p>
        <h2>文档与索引</h2>
        <p>服务器保存文档和任务状态；上传后会显式创建持久索引任务。</p>
      </div>
      <label v-if="store.knowledgeBases.length > 1" class="knowledge-selector">
        <span>知识库</span>
        <select v-model="store.selectedKnowledgeBaseId" aria-label="选择知识库">
          <option v-for="kb in store.knowledgeBases" :key="kb.id" :value="kb.id">{{ kb.name }}</option>
        </select>
      </label>
      <div v-else-if="store.knowledgeBases[0]" class="single-knowledge-base" aria-label="当前知识库">
        <span>当前知识库</span><strong>{{ store.knowledgeBases[0].name }}</strong>
      </div>
    </header>

    <KnowledgeUploadPanel :busy="store.uploading" @upload="upload" />

    <AppLoadingState v-if="store.loading" message="正在读取知识库与文档" />
    <AppErrorState v-else-if="store.errorMessage && store.documents.length === 0" :message="store.errorMessage" />
    <AppEmptyState v-else-if="store.documents.length === 0" title="暂无知识文档" description="上传 Markdown 或 PDF 后可查看实际切分与索引状态。" />
    <KnowledgeDocumentTable
      v-else
      :documents="store.documents"
      :tasks-by-document="store.tasksByDocument"
      :selected-document="store.selectedDocument"
      :previews-by-document="store.previewsByDocument"
      @select="selectDocument"
      @retry="retry"
      @rebuild="rebuild"
      @delete="store.requestDelete"
    />

    <section v-if="store.overwriteConfirmation" class="knowledge-confirmation" role="dialog" aria-modal="true" aria-label="确认覆盖文档">
      <strong>确认覆盖相同内容？</strong>
      <p>服务器已存在与 {{ store.overwriteConfirmation.filename }} 内容相同的文档。覆盖会软删除旧文档并按 owner scope 清理旧向量。</p>
      <div><button type="button" @click="store.cancelOverwrite">取消</button><button class="button button--primary" type="button" @click="confirmOverwrite">确认覆盖</button></div>
    </section>
    <section v-if="store.deleteConfirmation" class="knowledge-confirmation" role="dialog" aria-modal="true" aria-label="确认删除文档">
      <strong>确认删除 {{ store.deleteConfirmation.filename }}？</strong>
      <p>删除后将按当前 owner scope 清理该文档及其向量，操作完成后重新读取服务端列表。</p>
      <div><button type="button" @click="store.cancelDelete">取消</button><button class="button button--primary danger-button" type="button" @click="confirmDelete">确认删除</button></div>
    </section>
  </div>
</template>

<style scoped>
.knowledge-workspace { height: calc(100vh - 74px); min-width: 0; min-height: 0; display: grid; grid-template-rows: auto auto minmax(0, 1fr); gap: var(--space-4); padding: var(--space-5); overflow: hidden; }
.knowledge-heading { min-width: 0; display: flex; align-items: center; gap: var(--space-3); }
.knowledge-heading__icon { width: 44px; height: 44px; border: 1px solid #cfe0db; border-radius: 12px; display: grid; place-items: center; color: var(--color-accent); background: var(--color-accent-soft); }
.knowledge-heading h2 { margin: 3px 0; font-size: 23px; }
.knowledge-heading p:last-child { margin: 0; color: var(--color-text-muted); font-size: 12px; }
.knowledge-selector, .single-knowledge-base { margin-left: auto; display: grid; gap: 4px; color: var(--color-text-muted); font-size: 11px; }
.knowledge-selector select { min-width: 210px; height: 40px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0 10px; background: var(--color-surface); }
.single-knowledge-base strong { color: var(--color-text); font-size: 13px; }
.knowledge-confirmation { position: fixed; inset: 0; z-index: 30; width: min(460px, calc(100vw - 48px)); height: fit-content; margin: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md); display: grid; gap: var(--space-3); padding: var(--space-5); background: var(--color-surface); box-shadow: 0 0 0 100vmax rgb(23 32 38 / 35%), var(--shadow-panel); }
.knowledge-confirmation p { margin: 0; color: var(--color-text-muted); line-height: 1.65; }
.knowledge-confirmation > div { display: flex; justify-content: flex-end; gap: var(--space-2); }
.knowledge-confirmation > div > button:first-child { border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0 16px; background: white; cursor: pointer; }
.danger-button { background: var(--color-danger); }
</style>
