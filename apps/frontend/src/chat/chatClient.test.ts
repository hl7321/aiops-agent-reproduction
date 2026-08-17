import { describe, expect, it } from "vitest";

import { createApiClient } from "../transport/apiClient";
import { createChatClient } from "./chatClient";

describe("chatClient", () => {
  it("通过公共 ApiClient 调用六种服务端聊天操作", async () => {
    const calls: Array<{ url: string; method: string; body?: string }> = [];
    const api = createApiClient({ fetcher: async (input, init) => {
      calls.push({
        url: String(input), method: init?.method ?? "GET",
        ...(typeof init?.body === "string" ? { body: init.body } : {}),
      });
      const deleted = init?.method === "DELETE";
      return new Response(JSON.stringify({
        ok: true,
        data: deleted ? { deleted: true, sessionId: "s/1" } : {
          session: { id: "s/1", title: "新会话", createdAt: "now", updatedAt: "now" },
          messages: [],
          sessions: [],
        },
        meta: { requestId: "req-chat" },
      }), { headers: { "Content-Type": "application/json" } });
    }});
    const client = createChatClient(api);

    await client.createSession();
    await client.listSessions();
    await client.getSession("s/1");
    await client.appendMessage("s/1", { role: "user", content: "你好" });
    await client.clearMessages("s/1");
    await client.deleteSession("s/1");

    expect(calls).toEqual([
      { url: "/chat/sessions", method: "POST" },
      { url: "/chat/sessions", method: "GET" },
      { url: "/chat/sessions/s%2F1", method: "GET" },
      { url: "/chat/sessions/s%2F1/messages", method: "POST", body: '{"role":"user","content":"你好"}' },
      { url: "/chat/sessions/s%2F1/messages:clear", method: "POST" },
      { url: "/chat/sessions/s%2F1", method: "DELETE" },
    ]);
  });
});
