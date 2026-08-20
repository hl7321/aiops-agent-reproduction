import type {
  CreateMcpConnectionRequest,
  McpConnection,
  McpConnectionCheckResult,
  McpConnectionDeleteData,
  McpConnectionListData,
  UpdateMcpConnectionRequest,
} from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";

export interface McpClient {
  listConnections(): Promise<ApiResult<McpConnectionListData>>;
  createConnection(body: CreateMcpConnectionRequest): Promise<ApiResult<McpConnection>>;
  updateConnection(id: string, body: UpdateMcpConnectionRequest): Promise<ApiResult<McpConnection>>;
  deleteConnection(id: string): Promise<ApiResult<McpConnectionDeleteData>>;
  checkConnection(id: string): Promise<ApiResult<McpConnectionCheckResult>>;
}

export function createMcpClient(api: ApiClient): McpClient {
  const path = (id: string) => `/mcp/connections/${encodeURIComponent(id)}`;
  const json = (method: "POST" | "PUT", body: object): RequestInit => ({
    method,
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
  return {
    listConnections: () => api.request<McpConnectionListData>("/mcp/connections"),
    createConnection: (body) => api.request<McpConnection>(
      "/mcp/connections", json("POST", body),
    ),
    updateConnection: (id, body) => api.request<McpConnection>(path(id), json("PUT", body)),
    deleteConnection: (id) => api.request<McpConnectionDeleteData>(path(id), { method: "DELETE" }),
    checkConnection: (id) => api.request<McpConnectionCheckResult>(`${path(id)}:check`, {
      method: "POST",
    }),
  };
}
