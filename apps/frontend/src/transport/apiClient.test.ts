import { describe, expect, it, vi } from "vitest";

import type { FoundationStatus } from "@super-ai/api-contracts";

import { ApiClientError, createApiClient } from "./apiClient";

describe("apiClient", () => {
  it("解包成功 envelope 并返回 request ID", async () => {
    const client = createApiClient({
      fetcher: async () => new Response(JSON.stringify({
        ok: true,
        data: { status: "ok" },
        meta: { requestId: "req-success" },
      }), { status: 200, headers: { "Content-Type": "application/json" } }),
    });

    const result = await client.request<FoundationStatus>("/health");

    expect(result).toEqual({ data: { status: "ok" }, requestId: "req-success" });
  });

  it("把失败 envelope 转换为携带共享 error 的 typed 异常", async () => {
    const onUnauthorized = vi.fn();
    const client = createApiClient({
      onUnauthorized,
      fetcher: async () => new Response(JSON.stringify({
        ok: false,
        error: {
          code: "AUTH_REQUIRED",
          category: "authentication",
          httpStatus: 401,
          message: "需要认证后才能访问",
        },
        meta: { requestId: "req-auth" },
      }), { status: 401, headers: { "Content-Type": "application/json" } }),
    });

    const thrown = await client.request<FoundationStatus>("/health").catch((error: unknown) => error);

    expect(thrown).toBeInstanceOf(ApiClientError);
    expect(thrown).toMatchObject({
      requestId: "req-auth",
      error: {
        code: "AUTH_REQUIRED",
        category: "authentication",
        httpStatus: 401,
      },
    });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("通过扩展点注入 bearer token 和 request ID", async () => {
    let receivedUrl = "";
    let receivedHeaders = new Headers();
    const client = createApiClient({
      baseUrl: "/api",
      getAccessToken: () => "token-1",
      getRequestId: () => "req-client-1",
      fetcher: async (input, init) => {
        receivedUrl = String(input);
        receivedHeaders = new Headers(init?.headers);
        return new Response(JSON.stringify({
          ok: true,
          data: { status: "ok" },
          meta: { requestId: "req-client-1" },
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      },
    });

    await client.request<FoundationStatus>("/health");

    expect(receivedUrl).toBe("/api/health");
    expect(receivedHeaders.get("Authorization")).toBe("Bearer token-1");
    expect(receivedHeaders.get("X-Request-ID")).toBe("req-client-1");
  });

  it("拒绝不符合共享 envelope 的临时 payload", async () => {
    const client = createApiClient({
      fetcher: async () => new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    });

    await expect(client.request<FoundationStatus>("/health")).rejects.toThrow(
      "响应不符合共享 API envelope",
    );
  });

  it("为字符串 body 补 JSON Content-Type，且不覆盖显式类型或 FormData", async () => {
    const seen: Array<{ contentType: string | null }> = [];
    const client = createApiClient({
      fetcher: async (_input, init) => {
        const headers = new Headers(init?.headers);
        seen.push({ contentType: headers.get("Content-Type") });
        return new Response(JSON.stringify({
          ok: true,
          data: { status: "ok" },
          meta: { requestId: "req-body" },
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      },
    });

    await client.request<FoundationStatus>("/memory", {
      method: "PUT",
      body: JSON.stringify({ memoryMode: "manual" }),
    });
    await client.request<FoundationStatus>("/upload", {
      method: "POST",
      body: new FormData(),
    });
    await client.request<FoundationStatus>("/custom", {
      method: "PUT",
      body: "raw",
      headers: { "Content-Type": "application/merge-patch+json" },
    });

    expect(seen).toEqual([
      { contentType: "application/json" },
      { contentType: null },
      { contentType: "application/merge-patch+json" },
    ]);
  });
});
