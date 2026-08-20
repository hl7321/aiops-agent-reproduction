import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../transport/apiClient";
import { createMcpClient } from "./mcpClient";

describe("mcpClient", () => {
  it("使用受保护 JSON transport 调用 CRUD 与真实检查路径", async () => {
    const request = vi.fn(async (_input: string, _init?: RequestInit) => ({ data: {}, requestId: "req-1" }));
    const client = createMcpClient({ request } as unknown as ApiClient);
    const body = {
      name: "CLS", transport: "streamable_http" as const,
      url: "https://example.test/mcp", enabled: true, timeoutSeconds: 30, retries: 1,
    };

    await client.listConnections();
    await client.createConnection(body);
    await client.updateConnection("mcp/1", body);
    await client.checkConnection("mcp/1");
    await client.deleteConnection("mcp/1");

    expect(request.mock.calls.map((call) => call[0])).toEqual([
      "/mcp/connections", "/mcp/connections", "/mcp/connections/mcp%2F1",
      "/mcp/connections/mcp%2F1:check", "/mcp/connections/mcp%2F1",
    ]);
    expect(request.mock.calls[1]?.[1]).toMatchObject({ method: "POST" });
    expect(request.mock.calls[2]?.[1]).toMatchObject({ method: "PUT" });
    expect(request.mock.calls[3]?.[1]).toMatchObject({ method: "POST" });
    expect(request.mock.calls[4]?.[1]).toMatchObject({ method: "DELETE" });
  });
});
