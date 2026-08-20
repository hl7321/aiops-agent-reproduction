import type {
  AppendChatMessageRequest,
  AgentToolCallAuditListData,
  ChatDeleteData,
  ChatSessionDetailData,
  ChatSessionListData,
  ChatStreamMessageRequest,
  UpdateChatMemoryRequest,
  SseEvent,
} from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";
import type { SseClient } from "../transport/sseClient";

export interface ChatClient {
  createSession(): Promise<ApiResult<ChatSessionDetailData>>;
  listSessions(): Promise<ApiResult<ChatSessionListData>>;
  getSession(id: string): Promise<ApiResult<ChatSessionDetailData>>;
  appendMessage(id: string, body: AppendChatMessageRequest): Promise<ApiResult<ChatSessionDetailData>>;
  clearMessages(id: string): Promise<ApiResult<ChatSessionDetailData>>;
  updateMemory(id: string, body: UpdateChatMemoryRequest): Promise<ApiResult<ChatSessionDetailData>>;
  compactMemory(id: string): Promise<ApiResult<ChatSessionDetailData>>;
  deleteSession(id: string): Promise<ApiResult<ChatDeleteData>>;
  listToolCallAudits(id: string): Promise<ApiResult<AgentToolCallAuditListData>>;
  streamMessage(id: string, body: ChatStreamMessageRequest): AsyncIterable<SseEvent>;
}

export function createChatClient(api: ApiClient, sse: SseClient): ChatClient {
  const path = (id: string) => `/chat/sessions/${encodeURIComponent(id)}`;
  return {
    createSession: () => api.request<ChatSessionDetailData>("/chat/sessions", { method: "POST" }),
    listSessions: () => api.request<ChatSessionListData>("/chat/sessions"),
    getSession: (id) => api.request<ChatSessionDetailData>(path(id)),
    appendMessage: (id, body) => api.request<ChatSessionDetailData>(`${path(id)}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
    clearMessages: (id) => api.request<ChatSessionDetailData>(`${path(id)}/messages:clear`, {
      method: "POST",
    }),
    updateMemory: (id, body) => api.request<ChatSessionDetailData>(`${path(id)}/memory`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
    compactMemory: (id) => api.request<ChatSessionDetailData>(`${path(id)}/memory:compact`, {
      method: "POST",
    }),
    deleteSession: (id) => api.request<ChatDeleteData>(path(id), { method: "DELETE" }),
    listToolCallAudits: (id) =>
      api.request<AgentToolCallAuditListData>(`${path(id)}/tool-call-audits`),
    streamMessage: (id, body) => sse.stream(`${path(id)}/messages:stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  };
}
