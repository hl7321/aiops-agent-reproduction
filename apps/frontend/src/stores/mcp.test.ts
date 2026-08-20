import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { McpConnection, McpConnectionCheckResult } from "@super-ai/api-contracts";

import type { McpClient } from "../mcp/mcpClient";
import { createMcpStore } from "./mcp";

const connection: McpConnection = {
  id: "mcp-1", name: "CLS", transport: "streamable_http", url: "https://example.test/mcp",
  enabled: true, timeoutSeconds: 30, retries: 1, lastCheck: null, lastError: null,
  discoveredTools: [], createdAt: "2026-08-20T00:00:00Z", updatedAt: "2026-08-20T00:00:00Z",
};

function client(): McpClient {
  return {
    listConnections: vi.fn(async () => ({ data: { connections: [connection] }, requestId: "r1" })),
    createConnection: vi.fn(async (body) => ({ data: { ...connection, ...body }, requestId: "r2" })),
    updateConnection: vi.fn(async (id, body) => ({ data: { ...connection, ...body, id }, requestId: "r3" })),
    deleteConnection: vi.fn(async (id) => ({ data: { deleted: true as const, connectionId: id }, requestId: "r4" })),
    checkConnection: vi.fn(async () => ({
      data: {
        status: "connected", connection: { ...connection, discoveredTools: [{ name: "query_logs", description: "查询日志" }] },
        tools: [{ name: "query_logs", description: "查询日志" }], error: null,
      } satisfies McpConnectionCheckResult,
      requestId: "r5",
    })),
  };
}

describe("MCP store", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("以服务端 DTO 对账 CRUD、启停和检查结果", async () => {
    const fake = client();
    const useStore = createMcpStore({ client: fake });
    const store = useStore();
    await store.initialize();
    expect(store.connections).toEqual([connection]);

    await store.toggleEnabled("mcp-1", false);
    expect(store.connections[0]?.enabled).toBe(false);
    await store.check("mcp-1");
    expect(store.checkById["mcp-1"]?.status).toBe("connected");
    expect(store.connections[0]?.discoveredTools[0]?.name).toBe("query_logs");

    store.requestDelete("mcp-1");
    await store.confirmDelete();
    expect(store.connections).toEqual([]);
  });

  it("受保护清理会移除内存连接和表单状态", async () => {
    const store = createMcpStore({ client: client() })();
    await store.initialize();
    store.editingId = "mcp-1";
    store.reset();
    expect(store.connections).toEqual([]);
    expect(store.editingId).toBeNull();
    expect(store.checkById).toEqual({});
  });

  it("清理后忽略仍在途的旧认证世代响应", async () => {
    type ListResult = Awaited<ReturnType<McpClient["listConnections"]>>;
    let resolveList!: (value: ListResult) => void;
    const fake = client();
    fake.listConnections = vi.fn(
      () => new Promise<ListResult>((resolve) => { resolveList = resolve; }),
    );
    const store = createMcpStore({ client: fake })();

    const pending = store.initialize();
    store.reset();
    resolveList({ data: { connections: [connection] }, requestId: "stale" });
    await pending;

    expect(store.connections).toEqual([]);
    expect(store.loading).toBe(false);
  });

  it("更新连接后清除该连接的旧检查快照", async () => {
    const store = createMcpStore({ client: client() })();
    await store.initialize();
    await store.check("mcp-1");
    expect(store.checkById["mcp-1"]).toBeDefined();

    await store.update("mcp-1", {
      name: "CLS-new", transport: "sse", url: "https://example.test/sse",
      enabled: true, timeoutSeconds: 10, retries: 0,
    });

    expect(store.checkById["mcp-1"]).toBeUndefined();
  });
});
