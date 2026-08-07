import { isSseEvent } from "@super-ai/api-contracts";
import type { SseEvent } from "@super-ai/api-contracts";

import {
  buildTransportHeaders,
  resolveTransportUrl,
} from "./transportOptions";
import type { TransportOptions } from "./transportOptions";

export interface SseClientOptions extends TransportOptions {
  baseUrl?: string;
}

export interface SseClient {
  stream(input: string, init?: RequestInit): AsyncIterable<SseEvent>;
}

const FRAME_SEPARATOR = /\r\n\r\n|\n\n|\r\r/u;

export class SseFrameParser {
  private buffer = "";

  push(chunk: string): SseEvent[] {
    this.buffer += chunk;
    const events: SseEvent[] = [];
    let match = FRAME_SEPARATOR.exec(this.buffer);

    while (match !== null) {
      const frame = this.buffer.slice(0, match.index);
      this.buffer = this.buffer.slice(match.index + match[0].length);
      const event = parseFrame(frame);
      if (event !== undefined) {
        events.push(event);
      }
      match = FRAME_SEPARATOR.exec(this.buffer);
    }
    return events;
  }

  finish(): SseEvent[] {
    if (!this.buffer.trim()) {
      this.buffer = "";
      return [];
    }
    const frame = this.buffer;
    this.buffer = "";
    const event = parseFrame(frame);
    return event === undefined ? [] : [event];
  }
}

export function createSseClient(options: SseClientOptions = {}): SseClient {
  const fetcher = options.fetcher ?? globalThis.fetch;
  const baseUrl = options.baseUrl ?? "";

  return {
    async *stream(input: string, init: RequestInit = {}): AsyncIterable<SseEvent> {
      const headers = await buildTransportHeaders(init.headers, options, "text/event-stream");
      const response = await fetcher(resolveTransportUrl(baseUrl, input), { ...init, headers });
      if (!response.ok || response.body === null) {
        throw new Error(`SSE 连接失败: HTTP ${response.status}`);
      }

      const parser = new SseFrameParser();
      const decoder = new TextDecoder();
      const reader = response.body.getReader();
      try {
        while (true) {
          const result = await reader.read();
          if (result.done) {
            break;
          }
          for (const event of parser.push(decoder.decode(result.value, { stream: true }))) {
            yield event;
          }
        }
        const tail = decoder.decode();
        for (const event of parser.push(tail)) {
          yield event;
        }
        for (const event of parser.finish()) {
          yield event;
        }
      } finally {
        reader.releaseLock();
      }
    },
  };
}

function parseFrame(frame: string): SseEvent | undefined {
  const data = frame
    .replace(/\r\n|\r/gu, "\n")
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /u, ""));
  if (data.length === 0) {
    return undefined;
  }

  const payload: unknown = JSON.parse(data.join("\n"));
  if (!isSseEvent(payload)) {
    throw new TypeError("SSE data 不符合共享事件合同");
  }
  return payload;
}
