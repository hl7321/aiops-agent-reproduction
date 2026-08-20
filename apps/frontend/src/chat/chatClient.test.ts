import { describe, expect, it } from "vitest";

import { createApiClient } from "../transport/apiClient";
import { createSseClient } from "../transport/sseClient";
import { createChatClient } from "./chatClient";

describe("chatClient", () => {
  it("通过公共 ApiClient 调用会话与记忆操作", async () => {
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
          session: {
            id: "s/1", title: "新会话", memoryMode: "context_70_percent",
            memorySummary: null, contextTokens: 0, contextWindowTokens: 1000,
            contextUsagePercent: 0, compactedMessageCount: 0,
            lastCompactedAt: null, canCompact: false, createdAt: "now", updatedAt: "now",
          },
          messages: [],
          sessions: [],
        },
        meta: { requestId: "req-chat" },
      }), { headers: { "Content-Type": "application/json" } });
    }});
    const client = createChatClient(api, createSseClient({ fetcher: async () =>
      new Response(new ReadableStream({ start(controller) { controller.close(); } })) }));

    await client.createSession();
    await client.listSessions();
    await client.getSession("s/1");
    await client.appendMessage("s/1", { role: "user", content: "你好" });
    await client.clearMessages("s/1");
    await client.updateMemory("s/1", { memoryMode: "manual" });
    await client.compactMemory("s/1");
    await client.deleteSession("s/1");

    expect(calls).toEqual([
      { url: "/chat/sessions", method: "POST" },
      { url: "/chat/sessions", method: "GET" },
      { url: "/chat/sessions/s%2F1", method: "GET" },
      { url: "/chat/sessions/s%2F1/messages", method: "POST", body: '{"role":"user","content":"你好"}' },
      { url: "/chat/sessions/s%2F1/messages:clear", method: "POST" },
      { url: "/chat/sessions/s%2F1/memory", method: "PUT", body: '{"memoryMode":"manual"}' },
      { url: "/chat/sessions/s%2F1/memory:compact", method: "POST" },
      { url: "/chat/sessions/s%2F1", method: "DELETE" },
    ]);
  });

  it("通过共享 SseClient 发送 user-only stream 请求并保留事件 sequence", async () => {
    let received = { url: "", method: "", body: "", authorization: "", requestId: "" };
    const encoded = new TextEncoder().encode(
      'data: {"id":"turn-1:1","sequence":1,"type":"content.delta","channel":"chat","timestamp":"now","data":{"delta":"你"}}\n\n',
    );
    const sse = createSseClient({
      getAccessToken: () => "chat-token",
      getRequestId: () => "req-chat-stream",
      fetcher: async (input, init) => {
        const headers = new Headers(init?.headers);
        received = {
          url: String(input), method: init?.method ?? "GET", body: String(init?.body ?? ""),
          authorization: headers.get("Authorization") ?? "",
          requestId: headers.get("X-Request-ID") ?? "",
        };
        return new Response(new ReadableStream<Uint8Array>({
          start(controller) { controller.enqueue(encoded); controller.close(); },
        }), { status: 200 });
      },
    });
    const client = createChatClient(createApiClient(), sse);

    const events = [];
    for await (const event of client.streamMessage("s/1", { content: "你好" })) {
      events.push(event);
    }

    expect(received).toEqual({
      url: "/chat/sessions/s%2F1/messages:stream", method: "POST",
      body: '{"content":"你好"}', authorization: "Bearer chat-token",
      requestId: "req-chat-stream",
    });
    expect(events[0]?.sequence).toBe(1);
  });
});
