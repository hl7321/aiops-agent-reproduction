import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatSession, ChatSessionDetailData } from "@super-ai/api-contracts";

import type { ChatClient } from "../chat/chatClient";
import type { ApiResult } from "../transport/apiClient";
import { createChatStore } from "./chat";
import { clearProtectedStores, resetProtectedStoreRegistryForTests } from "./protectedStoreRegistry";

const SESSION: ChatSession = {
  id: "session-1", title: "新会话", createdAt: "now", updatedAt: "now",
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
    deleteSession: vi.fn(async () => result({ deleted: true as const, sessionId: SESSION.id })),
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
});
