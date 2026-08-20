import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  BackgroundJob,
  ChunkingConfig,
  ChunkPreviewData,
  DocumentIndexTask,
  KnowledgeBase,
  KnowledgeDocument,
} from "@super-ai/api-contracts";

import type { KnowledgeClient } from "../knowledge/knowledgeClient";
import { ApiClientError } from "../transport/apiClient";
import type { ApiResult } from "../transport/apiClient";
import {
  clearProtectedStores,
  resetProtectedStoreRegistryForTests,
} from "./protectedStoreRegistry";
import { createKnowledgeStore } from "./knowledge";

const KB: KnowledgeBase = { id: "kb-1", name: "默认知识库", isDefault: true };
const DOCUMENT: KnowledgeDocument = {
  id: "doc-1",
  knowledgeBaseId: KB.id,
  filename: "runbook.md",
  sizeBytes: 12,
  mimeType: "text/markdown",
  sha256: "hash-1",
  uploadedAt: "2026-08-16T00:00:00Z",
  indexStatus: "pending",
  chunkingConfig: { strategy: "paragraph" },
};
const TASK: DocumentIndexTask = {
  id: "task-1",
  knowledgeBaseId: KB.id,
  documentId: DOCUMENT.id,
  status: "pending",
  createdAt: "2026-08-16T00:00:00Z",
  updatedAt: "2026-08-16T00:00:00Z",
};

function result<T>(data: T): ApiResult<T> {
  return { data, requestId: "req-knowledge" };
}

function fakeClient(overrides: Partial<KnowledgeClient> = {}): KnowledgeClient {
  return {
    listKnowledgeBases: vi.fn(async () => result({ items: [KB] })),
    listDocuments: vi.fn(async () => result({ items: [DOCUMENT] })),
    getDocument: vi.fn(async () => result(DOCUMENT)),
    getChunkPreview: vi.fn(async () => result<ChunkPreviewData>({
      totalChunks: 1,
      items: [{ index: 0, excerpt: "正文", metadata: { heading: "概览" } }],
    })),
    uploadDocument: vi.fn(async () => result(DOCUMENT)),
    deleteDocument: vi.fn(async () => result(DOCUMENT)),
    createIndexTask: vi.fn(async () => result(TASK)),
    getIndexTask: vi.fn(async () => result(TASK)),
    retryIndexTask: vi.fn(async () => result({ ...TASK, id: "task-2", retryOfTaskId: TASK.id })),
    listBackgroundJobs: vi.fn(async () => result({ items: [] })),
    uploadAndCreateIndexTask: vi.fn(async () => ({
      document: DOCUMENT,
      task: TASK,
      uploadRequestId: "req-upload",
      taskRequestId: "req-task",
    })),
    ...overrides,
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  resetProtectedStoreRegistryForTests();
  vi.useRealTimers();
});

describe("knowledge store", () => {
  it("从服务器初始化并在受保护清理时移除全部 owner 数据与 timer", async () => {
    const client = fakeClient();
    const store = createKnowledgeStore({ client })();

    await store.initialize();
    expect(client.listKnowledgeBases).toHaveBeenCalledOnce();
    expect(client.listDocuments).toHaveBeenCalledWith(KB.id);
    expect(client.listBackgroundJobs).toHaveBeenCalledOnce();
    expect(store.knowledgeBases).toEqual([KB]);
    expect(store.documents).toEqual([DOCUMENT]);
    expect(store.selectedKnowledgeBaseId).toBe(KB.id);

    clearProtectedStores();
    expect(store.knowledgeBases).toEqual([]);
    expect(store.documents).toEqual([]);
    expect(store.tasksByDocument).toEqual({});
    expect(store.overwriteConfirmation).toBeNull();
  });

  it("logout 清理后忽略初始化请求的迟到 owner 数据", async () => {
    let resolveDocuments: ((value: ApiResult<{ items: readonly KnowledgeDocument[] }>) => void) | undefined;
    const pendingDocuments = new Promise<ApiResult<{ items: readonly KnowledgeDocument[] }>>(
      (resolve) => { resolveDocuments = resolve; },
    );
    const client = fakeClient({ listDocuments: vi.fn(() => pendingDocuments) });
    const store = createKnowledgeStore({ client })();

    const initialization = store.initialize();
    await vi.waitFor(() => expect(client.listDocuments).toHaveBeenCalledOnce());
    clearProtectedStores();
    resolveDocuments?.(result({ items: [DOCUMENT] }));
    await initialization;

    expect(store.knowledgeBases).toEqual([]);
    expect(store.documents).toEqual([]);
    expect(store.tasksByDocument).toEqual({});
  });

  it.each([
    [{ strategy: "fixed-character", maxCharacters: 1200, overlap: 200 } as const,
      { strategy: "fixed-character", maxCharacters: 1200, overlap: 200 }],
    [{ strategy: "markdown-heading" } as const, { strategy: "markdown-heading" }],
    [{ strategy: "paragraph" } as const, { strategy: "paragraph" }],
  ])("上传 %o 时发送精确策略并显式创建首次任务", async (config, expected) => {
    let uploadedForm: FormData | undefined;
    const client = fakeClient({
      uploadDocument: vi.fn(async (_kb, form) => {
        uploadedForm = form;
        return result(DOCUMENT);
      }),
    });
    const store = createKnowledgeStore({ client })();
    await store.initialize();

    await store.upload(new File(["正文"], "runbook.md", { type: "text/markdown" }), config);

    expect(JSON.parse(String(uploadedForm?.get("chunkingConfig")))).toEqual(expected);
    expect(uploadedForm?.get("overwrite")).toBe("false");
    expect(client.createIndexTask).toHaveBeenCalledWith(KB.id, DOCUMENT.id);
    expect(store.tasksByDocument[DOCUMENT.id]?.id).toBe(TASK.id);
  });

  it("从 background job 恢复最新任务并约每 2 秒 poll 到终态", async () => {
    vi.useFakeTimers();
    const jobs: readonly BackgroundJob[] = [{
      id: "job-1",
      ownerUserId: "user-1",
      kind: "document.index",
      resourceType: "document_index_task",
      resourceId: TASK.id,
      status: "running",
      payload: { taskId: TASK.id, knowledgeBaseId: KB.id, documentId: DOCUMENT.id },
      attempt: 1,
      maxAttempts: 3,
      timeoutSeconds: 600,
      availableAt: "2026-08-16T00:00:00Z",
      createdAt: "2026-08-16T00:00:00Z",
      updatedAt: "2026-08-16T00:00:01Z",
    }];
    const getIndexTask = vi.fn()
      .mockResolvedValueOnce(result({ ...TASK, status: "running" }))
      .mockResolvedValueOnce(result({ ...TASK, status: "succeeded" }));
    const client = fakeClient({
      listBackgroundJobs: vi.fn(async () => result({ items: jobs })),
      getIndexTask,
    });
    const store = createKnowledgeStore({ client, pollIntervalMs: 2_000 })();

    await store.initialize();
    expect(store.tasksByDocument[DOCUMENT.id]?.status).toBe("running");
    expect(getIndexTask).toHaveBeenCalledOnce();

    await vi.advanceTimersByTimeAsync(2_000);

    expect(getIndexTask).toHaveBeenCalledTimes(2);
    expect(store.tasksByDocument[DOCUMENT.id]?.status).toBe("succeeded");
    expect(client.listDocuments).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("失败任务 retry 返回新 attempt，任意非活动文档可手动重建", async () => {
    const failed = { ...TASK, status: "failed", failureReason: "向量服务不可用" } as const;
    const retry = { ...TASK, id: "task-2", status: "pending", retryOfTaskId: TASK.id } as const;
    const rebuilt = { ...TASK, id: "task-3", status: "pending" } as const;
    const client = fakeClient({
      getIndexTask: vi.fn(async () => result(failed)),
      retryIndexTask: vi.fn(async () => result(retry)),
      createIndexTask: vi.fn(async () => result(rebuilt)),
    });
    const store = createKnowledgeStore({ client })();
    await store.initialize();
    store.tasksByDocument[DOCUMENT.id] = failed;

    await store.retryTask(DOCUMENT.id);
    expect(client.retryIndexTask).toHaveBeenCalledWith(KB.id, DOCUMENT.id, TASK.id);
    expect(store.tasksByDocument[DOCUMENT.id]?.id).toBe("task-2");

    store.tasksByDocument[DOCUMENT.id] = { ...retry, status: "succeeded" };
    await store.rebuildDocument(DOCUMENT.id);
    expect(client.createIndexTask).toHaveBeenCalledWith(KB.id, DOCUMENT.id);
    expect(store.tasksByDocument[DOCUMENT.id]?.id).toBe("task-3");
  });

  it("hash 冲突只建立覆盖确认，确认覆盖和确认删除后刷新服务器列表", async () => {
    const conflict = new ApiClientError({
      code: "BUSINESS_CONFLICT",
      category: "business",
      httpStatus: 409,
      message: "相同内容已存在",
    }, "req-conflict");
    const uploadDocument = vi.fn()
      .mockRejectedValueOnce(conflict)
      .mockResolvedValueOnce(result(DOCUMENT));
    const client = fakeClient({ uploadDocument });
    const store = createKnowledgeStore({ client })();
    await store.initialize();
    const file = new File(["正文"], "runbook.md", { type: "text/markdown" });
    const config: ChunkingConfig = { strategy: "paragraph" };

    await store.upload(file, config);
    expect(store.overwriteConfirmation?.filename).toBe("runbook.md");
    expect(client.createIndexTask).not.toHaveBeenCalled();

    await store.confirmOverwrite();
    const replay = uploadDocument.mock.calls[1]?.[1] as FormData;
    expect(replay.get("overwrite")).toBe("true");
    expect(client.createIndexTask).toHaveBeenCalledOnce();
    expect(store.overwriteConfirmation).toBeNull();

    store.requestDelete(DOCUMENT.id);
    expect(store.deleteConfirmation?.id).toBe(DOCUMENT.id);
    await store.confirmDelete();
    expect(client.deleteDocument).toHaveBeenCalledWith(KB.id, DOCUMENT.id);
    expect(client.listDocuments).toHaveBeenCalledTimes(3);
    expect(store.deleteConfirmation).toBeNull();
  });
});
