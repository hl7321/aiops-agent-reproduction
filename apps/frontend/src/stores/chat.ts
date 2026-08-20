import { defineStore } from "pinia";
import { ref } from "vue";

import type {
  AppendChatMessageRequest,
  ChatStreamMessageRequest,
  ReferenceSourceEvent,
  ChatSession,
  ChatSessionDetailData,
  ChatMemoryMode,
  ToolCallEvent,
} from "@super-ai/api-contracts";

import type { ChatClient } from "../chat/chatClient";
import { createChatClient } from "../chat/chatClient";
import { publicConfig } from "../config";
import { createApiClient } from "../transport/apiClient";
import { createSseClient, SseClientError } from "../transport/sseClient";
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
    const liveContent = ref("");
    const liveReasoning = ref("");
    const liveToolCalls = ref<Record<string, ToolCallEvent["data"]>>({});
    const liveReferences = ref<readonly ReferenceSourceEvent["data"]["source"][]>([]);
    const liveStatus = ref<"idle" | "streaming" | "complete" | "error">("idle");
    const liveErrorMessage = ref<string | null>(null);

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

    async function updateMemoryMode(memoryMode: ChatMemoryMode): Promise<void> {
      const id = requireSelectedId();
      applyDetail((await dependencies.client.updateMemory(id, { memoryMode })).data);
    }

    async function compactMemory(): Promise<void> {
      const id = requireSelectedId();
      applyDetail((await dependencies.client.compactMemory(id)).data);
    }

    async function deleteSession(id: string): Promise<void> {
      const deleted = await dependencies.client.deleteSession(id);
      sessions.value = sessions.value.filter((session) => session.id !== deleted.data.sessionId);
      if (selectedDetail.value?.session.id === deleted.data.sessionId) selectedDetail.value = null;
    }

    async function streamMessage(body: ChatStreamMessageRequest): Promise<void> {
      const id = requireSelectedId();
      resetLive();
      liveStatus.value = "streaming";
      try {
        for await (const event of dependencies.client.streamMessage(id, body)) {
          if (event.type === "content.delta") liveContent.value += event.data.delta;
          else if (event.type === "reasoning.delta") liveReasoning.value += event.data.delta;
          else if (event.type === "tool.call") {
            liveToolCalls.value = { ...liveToolCalls.value, [event.data.toolCallId]: event.data };
          } else if (event.type === "reference.source") {
            liveReferences.value = [...liveReferences.value, event.data.source];
          } else if (event.type === "error") {
            liveStatus.value = "error";
            liveErrorMessage.value = event.data.error.message;
          } else if (event.type === "complete") {
            liveStatus.value = "complete";
          }
        }
        if (liveStatus.value === "complete") {
          applyDetail((await dependencies.client.getSession(id)).data);
        } else if (liveStatus.value === "streaming") {
          liveStatus.value = "error";
          liveErrorMessage.value = "流式响应未正常完成";
        }
      } catch (error: unknown) {
        if (error instanceof SseClientError && error.status === 401) {
          reset();
        } else {
          liveStatus.value = "error";
          liveErrorMessage.value = messageFrom(error);
        }
        throw error;
      }
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
      resetLive();
    }

    function resetLive(): void {
      liveContent.value = "";
      liveReasoning.value = "";
      liveToolCalls.value = {};
      liveReferences.value = [];
      liveStatus.value = "idle";
      liveErrorMessage.value = null;
    }

    registerProtectedStoreCleanup(reset);
    return {
      sessions, selectedDetail, loading, errorMessage,
      liveContent, liveReasoning, liveToolCalls, liveReferences, liveStatus, liveErrorMessage,
      initialize, createSession, selectSession, appendMessage, streamMessage,
      clearMessages, updateMemoryMode, compactMemory, deleteSession, reset,
    };
  });
}

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "聊天会话操作失败";
}

const browserTransportOptions = {
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => useAuthStore().clearLocalState(),
};
const browserChatClient = createChatClient(
  createApiClient(browserTransportOptions),
  createSseClient(browserTransportOptions),
);

export const useChatStore = createChatStore({ client: browserChatClient });
