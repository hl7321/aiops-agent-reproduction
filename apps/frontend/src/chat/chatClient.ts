import type {
  AppendChatMessageRequest,
  ChatDeleteData,
  ChatSessionDetailData,
  ChatSessionListData,
} from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";

export interface ChatClient {
  createSession(): Promise<ApiResult<ChatSessionDetailData>>;
  listSessions(): Promise<ApiResult<ChatSessionListData>>;
  getSession(id: string): Promise<ApiResult<ChatSessionDetailData>>;
  appendMessage(id: string, body: AppendChatMessageRequest): Promise<ApiResult<ChatSessionDetailData>>;
  clearMessages(id: string): Promise<ApiResult<ChatSessionDetailData>>;
  deleteSession(id: string): Promise<ApiResult<ChatDeleteData>>;
}

export function createChatClient(api: ApiClient): ChatClient {
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
    deleteSession: (id) => api.request<ChatDeleteData>(path(id), { method: "DELETE" }),
  };
}
