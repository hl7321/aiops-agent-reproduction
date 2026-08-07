import { ERROR_DEFINITIONS } from "./errors";
import type { ErrorCategory, ErrorCode } from "./errors";

export type JsonPrimitive = boolean | number | string | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export interface RequestMeta {
  requestId: string;
}

export interface SuccessEnvelope<T> {
  ok: true;
  data: T;
  meta: RequestMeta;
}

export interface ApiError {
  code: ErrorCode;
  category: ErrorCategory;
  httpStatus: number;
  message: string;
  details?: JsonValue;
}

export interface FailureEnvelope {
  ok: false;
  error: ApiError;
  meta: RequestMeta;
}

export type ApiEnvelope<T> = FailureEnvelope | SuccessEnvelope<T>;

export function isApiEnvelope<T = unknown>(value: unknown): value is ApiEnvelope<T> {
  if (!isRecord(value) || typeof value.ok !== "boolean" || !isRequestMeta(value.meta)) {
    return false;
  }
  if (value.ok) {
    return "data" in value;
  }
  return isApiError(value.error);
}

export function isApiError(value: unknown): value is ApiError {
  if (!isRecord(value)
    || typeof value.code !== "string"
    || !(value.code in ERROR_DEFINITIONS)
    || typeof value.message !== "string") {
    return false;
  }
  const definition = ERROR_DEFINITIONS[value.code as ErrorCode];
  return value.category === definition.category && value.httpStatus === definition.httpStatus;
}

function isRequestMeta(value: unknown): value is RequestMeta {
  return isRecord(value) && typeof value.requestId === "string" && value.requestId.length > 0;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
