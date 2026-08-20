import manifest from "../contract-manifest.json";

import type { ChatReference } from "./chat";
import { isApiError, isRecord } from "./http";
import type { ApiError, JsonValue } from "./http";

export const SSE_EVENT_TYPES = manifest.sse.eventTypes as readonly SseEventType[];
export const TOOL_CALL_LIFECYCLES =
  manifest.sse.toolCallLifecycles as readonly ToolCallLifecycle[];

export type SseEventType =
  | "complete"
  | "content.delta"
  | "error"
  | "reasoning.delta"
  | "reference.source"
  | "report"
  | "task.status"
  | "tool.call";

export type SseChannel = "aiops" | "chat";
export type ToolCallLifecycle = "completed" | "delta" | "failed" | "started";
export type TaskLifecycle = "completed" | "failed" | "queued" | "running";

export interface SseEventBase<TType extends SseEventType> {
  id: string;
  sequence: number;
  type: TType;
  channel: SseChannel;
  timestamp: string;
}

export interface ContentDeltaEvent extends SseEventBase<"content.delta"> {
  data: { delta: string };
}

export interface ReasoningDeltaEvent extends SseEventBase<"reasoning.delta"> {
  data: { delta: string };
}

export interface ToolCallEvent extends SseEventBase<"tool.call"> {
  data: {
    toolCallId: string;
    toolName: string;
    lifecycle: ToolCallLifecycle;
    input?: JsonValue;
    delta?: string;
    output?: JsonValue;
    error?: ApiError;
  };
}

export interface ReferenceSourceEvent extends SseEventBase<"reference.source"> {
  data: {
    source: ChatReference;
  };
}

export interface TaskStatusEvent extends SseEventBase<"task.status"> {
  data: {
    taskId: string;
    status: TaskLifecycle;
    message?: string;
  };
}

export interface ReportEvent extends SseEventBase<"report"> {
  data: { report: JsonValue };
}

export interface CompleteEvent extends SseEventBase<"complete"> {
  data: { finishReason: "cancelled" | "error" | "stop" };
}

export interface ErrorEvent extends SseEventBase<"error"> {
  data: { error: ApiError };
}

export type SseEvent =
  | CompleteEvent
  | ContentDeltaEvent
  | ErrorEvent
  | ReasoningDeltaEvent
  | ReferenceSourceEvent
  | ReportEvent
  | TaskStatusEvent
  | ToolCallEvent;

export function isSseEvent(value: unknown): value is SseEvent {
  if (!hasBaseFields(value) || !isRecord(value.data)) {
    return false;
  }
  const data = value.data;
  switch (value.type) {
    case "content.delta":
    case "reasoning.delta":
      return typeof data.delta === "string";
    case "tool.call":
      return typeof data.toolCallId === "string"
        && typeof data.toolName === "string"
        && typeof data.lifecycle === "string"
        && TOOL_CALL_LIFECYCLES.includes(data.lifecycle as ToolCallLifecycle);
    case "reference.source":
      return isChatReference(data.source);
    case "task.status":
      return typeof data.taskId === "string" && typeof data.status === "string";
    case "report":
      return "report" in data;
    case "complete":
      return data.finishReason === "stop"
        || data.finishReason === "error"
        || data.finishReason === "cancelled";
    case "error":
      return isApiError(data.error);
  }
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isChatReference(value: unknown): value is ChatReference {
  return isRecord(value)
    && typeof value.chunkId === "string"
    && typeof value.documentId === "string"
    && typeof value.knowledgeBaseId === "string"
    && typeof value.source === "string"
    && typeof value.excerpt === "string"
    && isRecord(value.metadata)
    && isNullableNumber(value.vectorRank)
    && isNullableNumber(value.vectorScore)
    && isNullableNumber(value.bm25Rank)
    && isNullableNumber(value.bm25Score)
    && typeof value.rrfScore === "number"
    && Number.isFinite(value.rrfScore)
    && typeof value.rerankRank === "number"
    && Number.isInteger(value.rerankRank)
    && typeof value.rerankScore === "number"
    && Number.isFinite(value.rerankScore)
    && value.score === value.rerankScore;
}

type SseEventCandidate = SseEventBase<SseEventType> & { data: unknown };

function hasBaseFields(value: unknown): value is SseEventCandidate {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.sequence === "number"
    && Number.isInteger(value.sequence)
    && value.sequence >= 1
    && typeof value.type === "string"
    && SSE_EVENT_TYPES.includes(value.type as SseEventType)
    && (value.channel === "chat" || value.channel === "aiops")
    && typeof value.timestamp === "string";
}
