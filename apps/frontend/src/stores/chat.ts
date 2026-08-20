import { defineStore } from "pinia";
import { ref } from "vue";

import type {
  AppendChatMessageRequest,
  AgentToolCallAudit,
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
  readonly sleep?: (milliseconds: number) => Promise<void>;
}

export function createChatStore(dependencies: ChatStoreDependencies) {
  return defineStore("chat", () => {
    const sessions = ref<readonly ChatSession[]>([]);
    const selectedDetail = ref<ChatSessionDetailData | null>(null);
    const toolAudits = ref<readonly AgentToolCallAudit[]>([]);
    const loading = ref(false);
    const errorMessage = ref<string | null>(null);
    const liveContent = ref("");
    const liveReasoning = ref("");
    const liveToolCalls = ref<Record<string, ToolCallEvent["data"]>>({});
    const liveReferences = ref<readonly ReferenceSourceEvent["data"]["source"][]>([]);
    const liveStatus = ref<"idle" | "streaming" | "complete" | "error">("idle");
    const liveErrorMessage = ref<string | null>(null);
    const sleep = dependencies.sleep ?? delay;
    let initializePromise: Promise<void> | undefined;
    let ensureActivePromise: Promise<void> | undefined;

    async function initialize(): Promise<void> {
      if (initializePromise !== undefined) return initializePromise;
      initializePromise = loadSessions();
      try {
        await initializePromise;
      } catch (error: unknown) {
        initializePromise = undefined;
        throw error;
      }
    }

    async function loadSessions(): Promise<void> {
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
      toolAudits.value = [];
      resetLive();
    }

    async function selectSession(id: string): Promise<void> {
      const [detail, audits] = await Promise.all([
        dependencies.client.getSession(id),
        dependencies.client.listToolCallAudits(id),
      ]);
      applyDetail(detail.data);
      toolAudits.value = audits.data.items;
      resetLive();
    }

    async function ensureActiveSession(): Promise<void> {
      if (ensureActivePromise !== undefined) return ensureActivePromise;
      ensureActivePromise = ensureActiveSessionOnce();
      try {
        await ensureActivePromise;
      } catch (error: unknown) {
        ensureActivePromise = undefined;
        throw error;
      }
    }

    async function ensureActiveSessionOnce(): Promise<void> {
      await initialize();
      if (selectedDetail.value !== null) return;
      const first = sessions.value[0];
      if (first === undefined) await createSession();
      else await selectSession(first.id);
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
      try {
        applyDetail((await dependencies.client.updateMemory(id, { memoryMode })).data);
      } catch (error: unknown) {
        await refreshDetail(id);
        throw error;
      }
    }

    async function compactMemory(): Promise<void> {
      const id = requireSelectedId();
      try {
        applyDetail((await dependencies.client.compactMemory(id)).data);
      } catch (error: unknown) {
        await refreshDetail(id);
        throw error;
      }
    }

    async function deleteSession(id: string): Promise<void> {
      const deleted = await dependencies.client.deleteSession(id);
      sessions.value = sessions.value.filter((session) => session.id !== deleted.data.sessionId);
      if (selectedDetail.value?.session.id !== deleted.data.sessionId) return;
      selectedDetail.value = null;
      toolAudits.value = [];
      resetLive();
      const next = sessions.value[0];
      if (next === undefined) await createSession();
      else await selectSession(next.id);
    }

    async function streamMessage(body: ChatStreamMessageRequest): Promise<void> {
      const id = requireSelectedId();
      resetLive();
      liveStatus.value = "streaming";
      try {
        for await (const event of dependencies.client.streamMessage(id, body)) {
          if (event.type === "content.delta") {
            for (const character of event.data.delta) {
              liveContent.value += character;
              await sleep(28);
            }
          }
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
          const [detail, audits] = await Promise.all([
            dependencies.client.getSession(id),
            dependencies.client.listToolCallAudits(id),
          ]);
          applyDetail(detail.data);
          toolAudits.value = audits.data.items;
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

    async function refreshDetail(id: string): Promise<void> {
      applyDetail((await dependencies.client.getSession(id)).data);
    }

    function requireSelectedId(): string {
      const id = selectedDetail.value?.session.id;
      if (id === undefined) throw new Error("尚未选择会话");
      return id;
    }

    function reset(): void {
      sessions.value = [];
      selectedDetail.value = null;
      toolAudits.value = [];
      loading.value = false;
      errorMessage.value = null;
      initializePromise = undefined;
      ensureActivePromise = undefined;
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
      sessions, selectedDetail, toolAudits, loading, errorMessage,
      liveContent, liveReasoning, liveToolCalls, liveReferences, liveStatus, liveErrorMessage,
      initialize, ensureActiveSession, createSession, selectSession, appendMessage, streamMessage,
      clearMessages, updateMemoryMode, compactMemory, deleteSession, reset,
    };
  });
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds));
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
