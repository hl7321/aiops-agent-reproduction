import { defineStore } from "pinia";
import { computed, ref } from "vue";

import type {
  BackgroundJob,
  ChunkingConfig,
  ChunkPreviewData,
  DocumentIndexTask,
  KnowledgeBase,
  KnowledgeDocument,
} from "@super-ai/api-contracts";
import { KNOWLEDGE_UPLOAD_POLICY } from "@super-ai/api-contracts";

import { publicConfig } from "../config";
import { createKnowledgeClient } from "../knowledge/knowledgeClient";
import type { KnowledgeClient } from "../knowledge/knowledgeClient";
import { ApiClientError, createApiClient } from "../transport/apiClient";
import { AUTH_TOKEN_STORAGE_KEY, useAuthStore } from "./auth";
import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

const ACTIVE_TASK_STATUSES = new Set<DocumentIndexTask["status"]>(["pending", "running"]);

interface UploadDraft {
  readonly file: File;
  readonly config: ChunkingConfig;
}

interface IndexJobPayload {
  readonly taskId: string;
  readonly knowledgeBaseId: string;
  readonly documentId: string;
}

export interface KnowledgeStoreDependencies {
  readonly client: KnowledgeClient;
  readonly pollIntervalMs?: number;
}

export function createKnowledgeStore(dependencies: KnowledgeStoreDependencies) {
  return defineStore("knowledge", () => {
    const knowledgeBases = ref<readonly KnowledgeBase[]>([]);
    const selectedKnowledgeBaseId = ref<string | null>(null);
    const documents = ref<readonly KnowledgeDocument[]>([]);
    const selectedDocument = ref<KnowledgeDocument | null>(null);
    const previewsByDocument = ref<Record<string, ChunkPreviewData>>({});
    const tasksByDocument = ref<Record<string, DocumentIndexTask>>({});
    const loading = ref(false);
    const uploading = ref(false);
    const errorMessage = ref<string | null>(null);
    const overwriteConfirmation = ref<{ readonly filename: string } | null>(null);
    const deleteConfirmation = ref<KnowledgeDocument | null>(null);
    const activeTaskCount = computed(() => Object.values(tasksByDocument.value)
      .filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length);
    const pollIntervalMs = dependencies.pollIntervalMs ?? 2_000;
    let overwriteDraft: UploadDraft | null = null;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let generation = 0;

    async function initialize(): Promise<void> {
      const currentGeneration = ++generation;
      clearPollTimer();
      loading.value = true;
      errorMessage.value = null;
      try {
        const bases = await dependencies.client.listKnowledgeBases();
        if (currentGeneration !== generation) return;
        knowledgeBases.value = bases.data.items;
        selectedKnowledgeBaseId.value = bases.data.items[0]?.id ?? null;
        if (selectedKnowledgeBaseId.value === null) {
          documents.value = [];
          return;
        }
        await refreshDocuments(currentGeneration);
        if (currentGeneration !== generation) return;
        await restoreIndexTasks(currentGeneration);
        if (currentGeneration !== generation) return;
        schedulePoll();
      } catch (error: unknown) {
        if (currentGeneration === generation) errorMessage.value = messageFrom(error);
        throw error;
      } finally {
        if (currentGeneration === generation) loading.value = false;
      }
    }

    async function refreshDocuments(expectedGeneration = generation): Promise<void> {
      const kb = requireKnowledgeBase();
      const response = await dependencies.client.listDocuments(kb);
      if (expectedGeneration !== generation) return;
      documents.value = response.data.items;
      if (selectedDocument.value !== null) {
        selectedDocument.value = response.data.items.find(
          (document) => document.id === selectedDocument.value?.id,
        ) ?? null;
      }
    }

    async function restoreIndexTasks(expectedGeneration = generation): Promise<void> {
      const kb = requireKnowledgeBase();
      const documentIds = new Set(documents.value.map((document) => document.id));
      const jobs = await dependencies.client.listBackgroundJobs();
      if (expectedGeneration !== generation) return;
      const latestByDocument = new Map<string, { job: BackgroundJob; payload: IndexJobPayload }>();
      for (const job of jobs.data.items) {
        const payload = parseIndexJob(job);
        if (payload === null || payload.knowledgeBaseId !== kb || !documentIds.has(payload.documentId)) {
          continue;
        }
        const previous = latestByDocument.get(payload.documentId);
        if (previous === undefined || previous.job.updatedAt.localeCompare(job.updatedAt) < 0) {
          latestByDocument.set(payload.documentId, { job, payload });
        }
      }
      const restored = await Promise.all([...latestByDocument.values()].map(async ({ payload }) =>
        (await dependencies.client.getIndexTask(
          payload.knowledgeBaseId,
          payload.documentId,
          payload.taskId,
        )).data,
      ));
      if (expectedGeneration !== generation) return;
      tasksByDocument.value = Object.fromEntries(restored.map((task) => [task.documentId, task]));
    }

    async function upload(file: File, config: ChunkingConfig): Promise<void> {
      overwriteDraft = { file, config };
      overwriteConfirmation.value = null;
      try {
        await performUpload(overwriteDraft, false);
      } catch (error: unknown) {
        if (isConflict(error)) {
          overwriteConfirmation.value = { filename: file.name };
          errorMessage.value = "检测到相同内容，请确认是否覆盖已有文档。";
          return;
        }
        overwriteDraft = null;
        errorMessage.value = messageFrom(error);
        throw error;
      }
    }

    async function confirmOverwrite(): Promise<void> {
      if (overwriteDraft === null) return;
      const draft = overwriteDraft;
      try {
        await performUpload(draft, true);
      } catch (error: unknown) {
        errorMessage.value = messageFrom(error);
        throw error;
      }
    }

    function cancelOverwrite(): void {
      overwriteDraft = null;
      overwriteConfirmation.value = null;
    }

    async function performUpload(draft: UploadDraft, overwrite: boolean): Promise<void> {
      const kb = requireKnowledgeBase();
      uploading.value = true;
      errorMessage.value = null;
      try {
        const uploaded = await dependencies.client.uploadDocument(
          kb,
          buildUploadForm(draft.file, draft.config, overwrite),
        );
        try {
          const created = await dependencies.client.createIndexTask(kb, uploaded.data.id);
          tasksByDocument.value[uploaded.data.id] = created.data;
        } finally {
          await refreshDocuments();
        }
        overwriteDraft = null;
        overwriteConfirmation.value = null;
        schedulePoll();
      } finally {
        uploading.value = false;
      }
    }

    async function loadDocument(documentId: string): Promise<void> {
      const kb = requireKnowledgeBase();
      selectedDocument.value = (await dependencies.client.getDocument(kb, documentId)).data;
    }

    async function loadPreview(documentId: string): Promise<void> {
      const kb = requireKnowledgeBase();
      previewsByDocument.value[documentId] = (
        await dependencies.client.getChunkPreview(kb, documentId)
      ).data;
    }

    async function retryTask(documentId: string): Promise<void> {
      const kb = requireKnowledgeBase();
      const current = tasksByDocument.value[documentId];
      if (current === undefined || (current.status !== "failed" && current.status !== "cancelled")) {
        throw new Error("当前索引任务不可重试");
      }
      const retried = await dependencies.client.retryIndexTask(kb, documentId, current.id);
      tasksByDocument.value[documentId] = retried.data;
      schedulePoll();
    }

    async function rebuildDocument(documentId: string): Promise<void> {
      const kb = requireKnowledgeBase();
      const current = tasksByDocument.value[documentId];
      if (current !== undefined && ACTIVE_TASK_STATUSES.has(current.status)) {
        throw new Error("文档正在索引，不能重复创建任务");
      }
      tasksByDocument.value[documentId] = (
        await dependencies.client.createIndexTask(kb, documentId)
      ).data;
      schedulePoll();
    }

    function requestDelete(documentId: string): void {
      deleteConfirmation.value = documents.value.find((document) => document.id === documentId) ?? null;
    }

    function cancelDelete(): void {
      deleteConfirmation.value = null;
    }

    async function confirmDelete(): Promise<void> {
      const target = deleteConfirmation.value;
      if (target === null) return;
      const kb = requireKnowledgeBase();
      await dependencies.client.deleteDocument(kb, target.id);
      if (selectedDocument.value?.id === target.id) selectedDocument.value = null;
      delete previewsByDocument.value[target.id];
      delete tasksByDocument.value[target.id];
      deleteConfirmation.value = null;
      await refreshDocuments();
      schedulePoll();
    }

    async function pollTasks(): Promise<void> {
      pollTimer = undefined;
      const currentGeneration = generation;
      const kb = selectedKnowledgeBaseId.value;
      if (kb === null) return;
      const active = Object.values(tasksByDocument.value).filter(
        (task) => ACTIVE_TASK_STATUSES.has(task.status),
      );
      if (active.length === 0) return;
      try {
        const refreshed = await Promise.all(active.map(async (task) =>
          (await dependencies.client.getIndexTask(kb, task.documentId, task.id)).data,
        ));
        if (currentGeneration !== generation) return;
        let reachedTerminal = false;
        for (const task of refreshed) {
          tasksByDocument.value[task.documentId] = task;
          reachedTerminal ||= !ACTIVE_TASK_STATUSES.has(task.status);
        }
        if (reachedTerminal) await refreshDocuments();
        errorMessage.value = null;
      } catch (error: unknown) {
        if (currentGeneration === generation) errorMessage.value = messageFrom(error);
      } finally {
        if (currentGeneration === generation) schedulePoll();
      }
    }

    function schedulePoll(): void {
      clearPollTimer();
      if (Object.values(tasksByDocument.value).some((task) => ACTIVE_TASK_STATUSES.has(task.status))) {
        pollTimer = setTimeout(() => { void pollTasks(); }, pollIntervalMs);
      }
    }

    function clearPollTimer(): void {
      if (pollTimer !== undefined) {
        clearTimeout(pollTimer);
        pollTimer = undefined;
      }
    }

    function reset(): void {
      generation += 1;
      clearPollTimer();
      knowledgeBases.value = [];
      selectedKnowledgeBaseId.value = null;
      documents.value = [];
      selectedDocument.value = null;
      previewsByDocument.value = {};
      tasksByDocument.value = {};
      loading.value = false;
      uploading.value = false;
      errorMessage.value = null;
      overwriteDraft = null;
      overwriteConfirmation.value = null;
      deleteConfirmation.value = null;
    }

    function requireKnowledgeBase(): string {
      if (selectedKnowledgeBaseId.value === null) throw new Error("没有可用的知识库");
      return selectedKnowledgeBaseId.value;
    }

    registerProtectedStoreCleanup(reset);

    return {
      knowledgeBases,
      selectedKnowledgeBaseId,
      documents,
      selectedDocument,
      previewsByDocument,
      tasksByDocument,
      loading,
      uploading,
      errorMessage,
      overwriteConfirmation,
      deleteConfirmation,
      activeTaskCount,
      initialize,
      refreshDocuments,
      upload,
      confirmOverwrite,
      cancelOverwrite,
      loadDocument,
      loadPreview,
      retryTask,
      rebuildDocument,
      requestDelete,
      cancelDelete,
      confirmDelete,
      reset,
    };
  });
}

function buildUploadForm(file: File, config: ChunkingConfig, overwrite: boolean): FormData {
  const form = new FormData();
  form.set(KNOWLEDGE_UPLOAD_POLICY.multipart.file, file);
  form.set(KNOWLEDGE_UPLOAD_POLICY.multipart.chunkingConfig, JSON.stringify(config));
  form.set(KNOWLEDGE_UPLOAD_POLICY.multipart.overwrite, String(overwrite));
  return form;
}

function parseIndexJob(job: BackgroundJob): IndexJobPayload | null {
  if (job.kind !== "document.index" || job.resourceType !== "document_index_task"
    || typeof job.resourceId !== "string" || !isRecord(job.payload)) {
    return null;
  }
  const { taskId, knowledgeBaseId, documentId } = job.payload;
  if (typeof taskId !== "string" || taskId !== job.resourceId
    || typeof knowledgeBaseId !== "string" || typeof documentId !== "string") {
    return null;
  }
  return { taskId, knowledgeBaseId, documentId };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isConflict(error: unknown): boolean {
  return error instanceof ApiClientError && error.error.code === "BUSINESS_CONFLICT";
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "知识库请求失败";
}

const browserClient = createKnowledgeClient(createApiClient({
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => useAuthStore().clearLocalState(),
}));

export const useKnowledgeStore = createKnowledgeStore({ client: browserClient });
