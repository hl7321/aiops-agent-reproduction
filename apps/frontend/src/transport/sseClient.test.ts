import { describe, expect, it } from "vitest";

import type { ErrorEvent, SseEvent, ToolCallEvent } from "@super-ai/api-contracts";

import { SseFrameParser, createSseClient } from "./sseClient";

const toolEvent: ToolCallEvent = {
  id: "evt-tool",
  sequence: 1,
  type: "tool.call",
  channel: "aiops",
  timestamp: "2026-08-07T12:00:00Z",
  data: {
    toolCallId: "call-1",
    toolName: "query_alerts",
    lifecycle: "delta",
    delta: "partial",
  },
};

const errorEvent: ErrorEvent = {
  id: "evt-error",
  sequence: 2,
  type: "error",
  channel: "chat",
  timestamp: "2026-08-07T12:00:01Z",
  data: {
    error: {
      code: "SYSTEM_INTERNAL_ERROR",
      category: "system",
      httpStatus: 500,
      message: "服务暂时不可用",
    },
  },
};

describe("SseFrameParser", () => {
  it("保留跨 chunk 的半帧并在补齐后产出共享事件", () => {
    const parser = new SseFrameParser();
    const serialized = JSON.stringify(toolEvent);

    expect(parser.push(`id: evt-tool\ndata: ${serialized.slice(0, 30)}`)).toEqual([]);
    expect(parser.push(`${serialized.slice(30)}\n\n`)).toEqual([toolEvent]);
  });

  it("从一个 chunk 解析多个 CRLF frame", () => {
    const parser = new SseFrameParser();
    const chunk = [toolEvent, errorEvent]
      .map((event) => `data: ${JSON.stringify(event)}\r\n\r\n`)
      .join("");

    expect(parser.push(chunk)).toEqual([toolEvent, errorEvent]);
  });

  it("合并同一 frame 中的多个 data 行", () => {
    const parser = new SseFrameParser();

    expect(parser.push('data: {"id":"evt-complete","sequence":3,\ndata: "type":"complete","channel":"chat","timestamp":"2026-08-07T12:00:02Z","data":{"finishReason":"stop"}}\n\n'))
      .toEqual([{
        id: "evt-complete",
        sequence: 3,
        type: "complete",
        channel: "chat",
        timestamp: "2026-08-07T12:00:02Z",
        data: { finishReason: "stop" },
      }]);
  });

  it("拒绝未知的私有事件 type", () => {
    const parser = new SseFrameParser();

    expect(() => parser.push('data: {"id":"evt-private","sequence":1,"type":"private.delta","channel":"chat","timestamp":"now","data":{}}\n\n'))
      .toThrow("SSE data 不符合共享事件合同");
  });

  it("401 时执行受保护状态清理扩展点", async () => {
    let cleaned = false;
    const client = createSseClient({
      onUnauthorized: () => { cleaned = true; },
      fetcher: async () => new Response("unauthorized", { status: 401 }),
    });

    await expect(async () => {
      for await (const _event of client.stream("/events")) {
        throw new Error("401 不应产生事件");
      }
    }).rejects.toThrow("HTTP 401");
    expect(cleaned).toBe(true);
  });
});

describe("sseClient", () => {
  it("通过共享扩展点注入 bearer token 和 request ID", async () => {
    let receivedHeaders = new Headers();
    const client = createSseClient({
      getAccessToken: () => "sse-token",
      getRequestId: () => "req-sse-1",
      fetcher: async (_input, init) => {
        receivedHeaders = new Headers(init?.headers);
        return new Response(new ReadableStream<Uint8Array>({
          start(controller) {
            controller.close();
          },
        }), { status: 200, headers: { "Content-Type": "text/event-stream" } });
      },
    });

    for await (const _event of client.stream("/events")) {
      throw new Error("空流不应产生事件");
    }

    expect(receivedHeaders.get("Authorization")).toBe("Bearer sse-token");
    expect(receivedHeaders.get("X-Request-ID")).toBe("req-sse-1");
  });

  it("用 streaming decoder 跨网络 chunk 返回 typed 事件", async () => {
    const encoded = new TextEncoder().encode(`data: ${JSON.stringify(errorEvent)}\n\n`);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoded.slice(0, 17));
        controller.enqueue(encoded.slice(17));
        controller.close();
      },
    });
    const client = createSseClient({
      fetcher: async () => new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    });
    const events: SseEvent[] = [];

    for await (const event of client.stream("/events")) {
      events.push(event);
    }

    expect(events).toEqual([errorEvent]);
  });
});
