import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AgentToolCallAudit,
  ChatMessage,
  ChatSession,
  ChatSessionDetailData,
  SseEvent,
} from "@super-ai/api-contracts";

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
const ASSISTANT: ChatMessage = {
  id: "assistant-1", sessionId: SESSION.id, role: "assistant", content: "你",
  sequence: 2, createdAt: "now", metadata: {
    references: [{
      chunkId: "chunk-1", documentId: "doc-1", knowledgeBaseId: "kb-1",
      source: "runbook.md", excerpt: "处理步骤", metadata: {},
      vectorRank: 1, vectorScore: 0.91, bm25Rank: null, bm25Score: null,
      rrfScore: 0.0164, rerankRank: 1, rerankScore: 0.97, score: 0.97,
    }],
    toolCallIds: ["call-1"],
  },
};
const AUDIT: AgentToolCallAudit = {
  id: "audit-1", toolCallId: "call-1", chatSessionId: SESSION.id,
  diagnosticTaskId: null, toolName: "knowledge_retrieval", arguments: { query: "secret" },
  status: "completed", resultSummary: "返回 1 条引用", errorMessage: null,
  startedAt: "now", completedAt: "later", durationMs: 12,
};
const result = <T>(data: T): ApiResult<T> => ({ data, requestId: "req-chat" });

function fakeClient(): ChatClient {
  return {
    listSessions: vi.fn(async () => result({ sessions: [SESSION] })),
    createSession: vi.fn(async () => result(DETAIL)),
    getSession: vi.fn(async () => result({ ...DETAIL, messages: [ASSISTANT] })),
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
    listToolCallAudits: vi.fn(async () => result({ items: [AUDIT] })),
    async *streamMessage(): AsyncIterable<SseEvent> {
      yield {
        id: "turn-1:1", sequence: 1, type: "tool.call", channel: "chat", timestamp: "now",
        data: { toolCallId: "call-1", toolName: "knowledge_retrieval", lifecycle: "started" },
      };
      yield {
        id: "turn-1:2", sequence: 2, type: "reference.source", channel: "chat", timestamp: "now",
        data: { source: {
          chunkId: "chunk-1", documentId: "doc-1", knowledgeBaseId: "kb-1",
          source: "runbook.md", excerpt: "处理步骤", metadata: {},
          vectorRank: 1, vectorScore: 0.91, bm25Rank: null, bm25Score: null,
          rrfScore: 0.0164, rerankRank: 1, rerankScore: 0.97, score: 0.97,
        } },
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
afterEach(() => vi.useRealTimers());

describe("chat store", () => {
  it("以服务端响应对账并在受保护清理时移除 owner 数据", async () => {
    const client = fakeClient();
    const store = createChatStore({ client })();

    await store.initialize();
    await store.selectSession(SESSION.id);
    expect(store.toolAudits).toEqual([AUDIT]);
    await store.appendMessage({ role: "user", content: "你好" });
    expect(store.selectedDetail?.messages[0]?.content).toBe("你好");
    expect(store.sessions[0]?.title).toBe("你好");

    await store.clearMessages();
    expect(store.selectedDetail?.messages).toEqual([]);
    await store.deleteSession(SESSION.id);
    expect(client.createSession).toHaveBeenCalledTimes(1);
    expect(store.selectedDetail?.session.id).toBe(SESSION.id);

    await store.initialize();
    clearProtectedStores();
    expect(store.sessions).toEqual([]);
    expect(store.selectedDetail).toBeNull();
  });

  it("initialize 只读取一次并能确定性确保活动会话", async () => {
    const client = fakeClient();
    const store = createChatStore({ client })();
    await Promise.all([store.initialize(), store.initialize()]);
    await store.ensureActiveSession();
    expect(client.listSessions).toHaveBeenCalledTimes(1);
    expect(client.getSession).toHaveBeenCalledWith(SESSION.id);
  });

  it("并发 ensureActiveSession 只创建一次活动会话", async () => {
    const client = fakeClient();
    client.listSessions = vi.fn(async () => result({ sessions: [] }));
    const store = createChatStore({ client })();
    await Promise.all([store.ensureActiveSession(), store.ensureActiveSession()]);
    expect(client.listSessions).toHaveBeenCalledTimes(1);
    expect(client.createSession).toHaveBeenCalledTimes(1);
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

  it("记忆写操作失败后重新读取最后成功的服务端 DTO", async () => {
    const client = fakeClient();
    client.updateMemory = vi.fn(async () => { throw new Error("更新失败"); });
    const store = createChatStore({ client })();
    await store.selectSession(SESSION.id);
    await expect(store.updateMemoryMode("manual")).rejects.toThrow("更新失败");
    expect(client.getSession).toHaveBeenCalledTimes(2);
    expect(store.selectedDetail?.session.memoryMode).toBe("context_70_percent");
  });

  it("按共享 SSE union 累计当前轮状态并在新一轮开始时清理引用", async () => {
    const sleep = vi.fn(async () => undefined);
    const client = fakeClient();
    const store = createChatStore({ client, sleep })();
    await store.selectSession(SESSION.id);

    await store.streamMessage({ content: "第一轮" });

    expect(store.liveContent).toBe("你");
    expect(store.liveReferences[0]?.chunkId).toBe("chunk-1");
    expect(store.liveReferences[0]?.rerankScore).toBe(0.97);
    expect(store.liveToolCalls["call-1"]?.lifecycle).toBe("started");
    expect(store.liveStatus).toBe("complete");
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(sleep).toHaveBeenCalledWith(28);
    expect(client.getSession).toHaveBeenCalledTimes(2);
    expect(client.listToolCallAudits).toHaveBeenCalledTimes(2);
    expect(store.selectedDetail?.messages).toEqual([ASSISTANT]);
    expect(store.toolAudits).toEqual([AUDIT]);

    const pending = store.streamMessage({ content: "第二轮" });
    expect(store.liveReferences).toEqual([]);
    await pending;
  });

  it("默认串行读取在每个 Unicode 正文字符后等待约 28ms", async () => {
    vi.useFakeTimers();
    const client = fakeClient();
    client.streamMessage = async function* (): AsyncIterable<SseEvent> {
      yield {
        id: "turn-delay:1", sequence: 1, type: "content.delta", channel: "chat", timestamp: "now",
        data: { delta: "中🙂" },
      };
      yield {
        id: "turn-delay:2", sequence: 2, type: "complete", channel: "chat", timestamp: "now",
        data: { finishReason: "stop" },
      };
    };
    const store = createChatStore({ client })();
    await store.selectSession(SESSION.id);
    const pending = store.streamMessage({ content: "延迟" });
    await vi.advanceTimersByTimeAsync(27);
    expect(store.liveContent).toBe("中");
    await vi.advanceTimersByTimeAsync(1);
    expect(store.liveContent).toBe("中🙂");
    await vi.advanceTimersByTimeAsync(28);
    await pending;
    expect(store.liveStatus).toBe("complete");
  });

  it("删除活动会话后选择剩余会话，没有剩余时创建新会话", async () => {
    const client = fakeClient();
    const second = { ...SESSION, id: "session-2", title: "第二个" };
    client.listSessions = vi.fn(async () => result({ sessions: [SESSION, second] }));
    client.getSession = vi.fn(async (id) => result({
      session: id === second.id ? second : SESSION, messages: [],
    }));
    client.deleteSession = vi.fn(async (id) => result({ deleted: true as const, sessionId: id }));
    const store = createChatStore({ client })();
    await store.initialize();
    await store.selectSession(SESSION.id);
    await store.deleteSession(SESSION.id);
    expect(store.selectedDetail?.session.id).toBe(second.id);

    await store.deleteSession(second.id);
    expect(client.createSession).toHaveBeenCalledTimes(1);
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
