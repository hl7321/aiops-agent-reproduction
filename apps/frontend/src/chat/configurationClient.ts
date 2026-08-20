import type {
  ChatAssetDeleteData,
  ChatConfigurationData,
  CreateChatPromptRequest,
  UpdateChatConfigurationRequest,
  UpdateChatPromptRequest,
} from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";

export interface ChatConfigurationClient {
  getConfiguration(): Promise<ApiResult<ChatConfigurationData>>;
  updateConfiguration(body: UpdateChatConfigurationRequest): Promise<ApiResult<ChatConfigurationData>>;
  createPrompt(body: CreateChatPromptRequest): Promise<ApiResult<ChatConfigurationData>>;
  updatePrompt(id: string, body: UpdateChatPromptRequest): Promise<ApiResult<ChatConfigurationData>>;
  deletePrompt(id: string): Promise<ApiResult<ChatAssetDeleteData>>;
  uploadSkill(form: FormData): Promise<ApiResult<ChatConfigurationData>>;
  deleteSkill(id: string): Promise<ApiResult<ChatAssetDeleteData>>;
}

export function createChatConfigurationClient(api: ApiClient): ChatConfigurationClient {
  const promptPath = (id: string) => `/chat/prompts/${encodeURIComponent(id)}`;
  const skillPath = (id: string) => `/chat/skills/${encodeURIComponent(id)}`;
  return {
    getConfiguration: () => api.request<ChatConfigurationData>("/chat/configuration"),
    updateConfiguration: (body) => api.request<ChatConfigurationData>("/chat/configuration", {
      method: "PUT", body: JSON.stringify(body), headers: { "Content-Type": "application/json" },
    }),
    createPrompt: (body) => api.request<ChatConfigurationData>("/chat/prompts", {
      method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" },
    }),
    updatePrompt: (id, body) => api.request<ChatConfigurationData>(promptPath(id), {
      method: "PUT", body: JSON.stringify(body), headers: { "Content-Type": "application/json" },
    }),
    deletePrompt: (id) => api.request<ChatAssetDeleteData>(promptPath(id), { method: "DELETE" }),
    uploadSkill: (form) => api.request<ChatConfigurationData>("/chat/skills", {
      method: "POST", body: form,
    }),
    deleteSkill: (id) => api.request<ChatAssetDeleteData>(skillPath(id), { method: "DELETE" }),
  };
}
