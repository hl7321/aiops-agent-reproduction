import { defineStore } from "pinia";
import { ref } from "vue";

import type {
  AppendChatMessageRequest,
  ChatSession,
  ChatSessionDetailData,
} from "@super-ai/api-contracts";

import type { ChatClient } from "../chat/chatClient";
import { createChatClient } from "../chat/chatClient";
import { publicConfig } from "../config";
import { createApiClient } from "../transport/apiClient";
import { AUTH_TOKEN_STORAGE_KEY, useAuthStore } from "./auth";
import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

export interface ChatStoreDependencies {
  readonly client: ChatClient;
}

export function createChatStore(dependencies: ChatStoreDependencies) {
  return defineStore("chat", () => {
    const sessions = ref<readonly ChatSession[]>([]);
    const selectedDetail = ref<ChatSessionDetailData | null>(null);
    const loading = ref(false);
    const errorMessage = ref<string | null>(null);

    async function initialize(): Promise<void> {
      loading.value = true;
      errorMessage.value = null;
      try {
        sessions.value = (await dependencies.client.listSessions()).data.sessions;
      } catch (error: unknown) {
        errorMessage.value = messageFrom(error);
        throw error;
      } finally {
        loading.value = false;
      }
    }

    async function createSession(): Promise<void> {
      applyDetail((await dependencies.client.createSession()).data);
    }

    async function selectSession(id: string): Promise<void> {
      applyDetail((await dependencies.client.getSession(id)).data);
    }

    async function appendMessage(body: AppendChatMessageRequest): Promise<void> {
      const id = requireSelectedId();
      applyDetail((await dependencies.client.appendMessage(id, body)).data);
    }

    async function clearMessages(): Promise<void> {
      const id = requireSelectedId();
      applyDetail((await dependencies.client.clearMessages(id)).data);
    }

    async function deleteSession(id: string): Promise<void> {
      const deleted = await dependencies.client.deleteSession(id);
      sessions.value = sessions.value.filter((session) => session.id !== deleted.data.sessionId);
      if (selectedDetail.value?.session.id === deleted.data.sessionId) selectedDetail.value = null;
    }

    function applyDetail(detail: ChatSessionDetailData): void {
      selectedDetail.value = detail;
      sessions.value = [
        detail.session,
        ...sessions.value.filter((session) => session.id !== detail.session.id),
      ];
    }

    function requireSelectedId(): string {
      const id = selectedDetail.value?.session.id;
      if (id === undefined) throw new Error("尚未选择会话");
      return id;
    }

    function reset(): void {
      sessions.value = [];
      selectedDetail.value = null;
      loading.value = false;
      errorMessage.value = null;
    }

    registerProtectedStoreCleanup(reset);
    return {
      sessions, selectedDetail, loading, errorMessage,
      initialize, createSession, selectSession, appendMessage, clearMessages, deleteSession, reset,
    };
  });
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "聊天会话操作失败";
}

const browserChatClient = createChatClient(createApiClient({
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => useAuthStore().clearLocalState(),
}));

export const useChatStore = createChatStore({ client: browserChatClient });
