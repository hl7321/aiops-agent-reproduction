import type { DocumentIndexTask, KnowledgeDocument } from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";

export interface UploadAndIndexResult {
  readonly document: KnowledgeDocument;
  readonly task: DocumentIndexTask;
  readonly uploadRequestId: string;
  readonly taskRequestId: string;
}

export interface KnowledgeClient {
  uploadDocument(kb: string, form: FormData): Promise<ApiResult<KnowledgeDocument>>;
  createIndexTask(kb: string, document: string): Promise<ApiResult<DocumentIndexTask>>;
  getIndexTask(kb: string, document: string, task: string): Promise<ApiResult<DocumentIndexTask>>;
  retryIndexTask(kb: string, document: string, task: string): Promise<ApiResult<DocumentIndexTask>>;
  uploadAndCreateIndexTask(kb: string, form: FormData): Promise<UploadAndIndexResult>;
}

export function createKnowledgeClient(api: ApiClient): KnowledgeClient {
  const uploadDocument = (kb: string, form: FormData) =>
    api.request<KnowledgeDocument>(`/knowledge-bases/${encodeURIComponent(kb)}/documents`, {
      method: "POST",
      body: form,
    });
  const createIndexTask = (kb: string, document: string) =>
    api.request<DocumentIndexTask>(
      `/knowledge-bases/${encodeURIComponent(kb)}/documents/${encodeURIComponent(document)}/index-tasks`,
      { method: "POST" },
    );
  return {
    uploadDocument,
    createIndexTask,
    getIndexTask: (kb, document, task) => api.request<DocumentIndexTask>(
      `/knowledge-bases/${encodeURIComponent(kb)}/documents/${encodeURIComponent(document)}/index-tasks/${encodeURIComponent(task)}`,
    ),
    retryIndexTask: (kb, document, task) => api.request<DocumentIndexTask>(
      `/knowledge-bases/${encodeURIComponent(kb)}/documents/${encodeURIComponent(document)}/index-tasks/${encodeURIComponent(task)}:retry`,
      { method: "POST" },
    ),
    async uploadAndCreateIndexTask(kb, form) {
      const uploaded = await uploadDocument(kb, form);
      const created = await createIndexTask(kb, uploaded.data.id);
      return {
        document: uploaded.data,
        task: created.data,
        uploadRequestId: uploaded.requestId,
        taskRequestId: created.requestId,
      };
    },
  };
}
