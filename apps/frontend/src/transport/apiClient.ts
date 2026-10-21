import { isApiEnvelope } from "@super-ai/api-contracts";
import type { ApiError } from "@super-ai/api-contracts";

import {
  buildTransportHeaders,
  resolveTransportUrl,
} from "./transportOptions";
import type { TransportOptions } from "./transportOptions";

export interface ApiClientOptions extends TransportOptions {
  baseUrl?: string;
  onUnauthorized?: (error: ApiClientError) => void | Promise<void>;
}

export interface ApiResult<T> {
  data: T;
  requestId: string;
}

export interface ApiClient {
  request<T>(input: string, init?: RequestInit): Promise<ApiResult<T>>;
}

export class ApiClientError extends Error {
  readonly error: ApiError;
  readonly requestId: string;

  constructor(error: ApiError, requestId: string) {
    super(error.message);
    this.name = "ApiClientError";
    this.error = error;
    this.requestId = requestId;
  }
}

export function createApiClient(options: ApiClientOptions = {}): ApiClient {
  const fetcher = options.fetcher ?? globalThis.fetch;
  const baseUrl = options.baseUrl ?? "";

  return {
    async request<T>(input: string, init: RequestInit = {}): Promise<ApiResult<T>> {
      const headers = await buildTransportHeaders(init.headers, options, "application/json");
      // fetch 对字符串 body 默认发 text/plain，FastAPI 不会把它解析成 Pydantic body。
      // 只对字符串 JSON body 补 Content-Type，FormData/Blob 与显式类型保持原样。
      if (typeof init.body === "string" && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      const response = await fetcher(resolveTransportUrl(baseUrl, input), { ...init, headers });
      const payload: unknown = await response.json();

      if (!isApiEnvelope<T>(payload)) {
        throw new TypeError("响应不符合共享 API envelope");
      }
      if (!payload.ok) {
        const error = new ApiClientError(payload.error, payload.meta.requestId);
        if (payload.error.httpStatus === 401) {
          await options.onUnauthorized?.(error);
        }
        throw error;
      }
      return { data: payload.data, requestId: payload.meta.requestId };
    },
  };
}
