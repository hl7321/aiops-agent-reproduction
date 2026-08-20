import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatSession, ChatSessionDetailData, SseEvent } from "@super-ai/api-contracts";

import type { ChatClient } from "../chat/chatClient";
import type { ApiResult } from "../transport/apiClient";
import { SseClientError } from "../transport/sseClient";
import { createChatStore } from "./chat";
import { clearProtectedStores, resetProtectedStoreRegistryForTests } from "./protectedStoreRegistry";

const SESSION: ChatSession = {
  id: "session-1", title: "新会话", memoryMode: "context_70_percent",
  memorySummary: null, contextTokens: 0, contextWindowTokens: 1000,
  contextUsagePercent: 0, compactedMessageCount: 0, lastCompactedAt: null,
  canCompact: false, createdAt: "now", updatedAt: "now",
};
const DETAIL: ChatSessionDetailData = { session: SESSION, messages: [] };
const result = <T>(data: T): ApiResult<T> => ({ data, requestId: "req-chat" });

function fakeClient(): ChatClient {
  return {
    listSessions: vi.fn(async () => result({ sessions: [SESSION] })),
    createSession: vi.fn(async () => result(DETAIL)),
    getSession: vi.fn(async () => result(DETAIL)),
    appendMessage: vi.fn(async () => result<ChatSessionDetailData>({
      session: { ...SESSION, title: "你好" },
      messages: [{
        id: "message-1", sessionId: SESSION.id, role: "user", content: "你好",
        sequence: 1, metadata: {}, createdAt: "now",
      }],
    })),
    clearMessages: vi.fn(async () => result(DETAIL)),
    updateMemory: vi.fn(async (_id, body) => result({
      ...DETAIL, session: { ...SESSION, memoryMode: body.memoryMode },
    })),
    compactMemory: vi.fn(async () => result({
      ...DETAIL,
      session: {
        ...SESSION, memorySummary: "摘要", compactedMessageCount: 2,
        lastCompactedAt: "later", contextTokens: 20,
      },
    })),
    deleteSession: vi.fn(async () => result({ deleted: true as const, sessionId: SESSION.id })),
    listToolCallAudits: vi.fn(async () => result({ items: [] })),
    async *streamMessage(): AsyncIterable<SseEvent> {
      yield {
        id: "turn-1:1", sequence: 1, type: "tool.call", channel: "chat", timestamp: "now",
        data: { toolCallId: "call-1", toolName: "knowledge_retrieval", lifecycle: "started" },
      };
      yield {
        id: "turn-1:2", sequence: 2, type: "reference.source", channel: "chat", timestamp: "now",
        data: { source: { id: "chunk-1", title: "runbook.md" } },
      };
      yield {
        id: "turn-1:3", sequence: 3, type: "content.delta", channel: "chat", timestamp: "now",
        data: { delta: "你" },
      };
      yield {
        id: "turn-1:4", sequence: 4, type: "complete", channel: "chat", timestamp: "now",
        data: { finishReason: "stop" },
      };
    },
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  resetProtectedStoreRegistryForTests();
});

describe("chat store", () => {
  it("以服务端响应对账并在受保护清理时移除 owner 数据", async () => {
    const client = fakeClient();
    const store = createChatStore({ client })();

    await store.initialize();
    await store.selectSession(SESSION.id);
    await store.appendMessage({ role: "user", content: "你好" });
    expect(store.selectedDetail?.messages[0]?.content).toBe("你好");
    expect(store.sessions[0]?.title).toBe("你好");

    await store.clearMessages();
    expect(store.selectedDetail?.messages).toEqual([]);
    await store.deleteSession(SESSION.id);
    expect(store.sessions).toEqual([]);
    expect(store.selectedDetail).toBeNull();

    await store.initialize();
    clearProtectedStores();
    expect(store.sessions).toEqual([]);
    expect(store.selectedDetail).toBeNull();
  });

  it("以服务端详情对账记忆模式与手动压缩结果", async () => {
    const client = fakeClient();
    const store = createChatStore({ client })();
    await store.selectSession(SESSION.id);

    await store.updateMemoryMode("manual");
    expect(store.selectedDetail?.session.memoryMode).toBe("manual");
    expect(store.sessions[0]?.memoryMode).toBe("manual");

    await store.compactMemory();
    expect(store.selectedDetail?.session.memorySummary).toBe("摘要");
    expect(store.sessions[0]?.compactedMessageCount).toBe(2);
  });

  it("按共享 SSE union 累计当前轮状态并在新一轮开始时清理引用", async () => {
    const store = createChatStore({ client: fakeClient() })();
    await store.selectSession(SESSION.id);

    await store.streamMessage({ content: "第一轮" });

    expect(store.liveContent).toBe("你");
    expect(store.liveReferences).toEqual([{ id: "chunk-1", title: "runbook.md" }]);
    expect(store.liveToolCalls["call-1"]?.lifecycle).toBe("started");
    expect(store.liveStatus).toBe("complete");

    const pending = store.streamMessage({ content: "第二轮" });
    expect(store.liveReferences).toEqual([]);
    await pending;
  });

  it("stream 401 清除会话与当前轮 owner 数据", async () => {
    const client = fakeClient();
    client.streamMessage = async function* (): AsyncIterable<SseEvent> {
      throw new SseClientError(401);
    };
    const store = createChatStore({ client })();
    await store.initialize();
    await store.selectSession(SESSION.id);

    await expect(store.streamMessage({ content: "认证失效" })).rejects.toThrow("HTTP 401");

    expect(store.sessions).toEqual([]);
    expect(store.selectedDetail).toBeNull();
    expect(store.liveContent).toBe("");
    expect(store.liveStatus).toBe("idle");
  });
});
