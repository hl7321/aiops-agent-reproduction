export type McpTransport = "sse" | "streamable_http";
export type McpConnectionCheckStatus = "connected" | "failed";

export interface McpDiscoveredTool {
  readonly name: string;
  readonly description: string | null;
}

export interface McpConnection {
  readonly id: string;
  readonly name: string;
  readonly transport: McpTransport;
  readonly url: string;
  readonly enabled: boolean;
  readonly timeoutSeconds: number;
  readonly retries: number;
  readonly lastCheck: string | null;
  readonly lastError: string | null;
  readonly discoveredTools: readonly McpDiscoveredTool[];
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface McpConnectionListData {
  readonly connections: readonly McpConnection[];
}

export interface CreateMcpConnectionRequest {
  readonly name: string;
  readonly transport: McpTransport;
  readonly url: string;
  readonly enabled: boolean;
  readonly timeoutSeconds: number;
  readonly retries: number;
}

export type UpdateMcpConnectionRequest = CreateMcpConnectionRequest;

export interface McpConnectionDeleteData {
  readonly deleted: true;
  readonly connectionId: string;
}

export interface McpConnectionCheckResult {
  readonly status: McpConnectionCheckStatus;
  readonly connection: McpConnection;
  readonly tools: readonly McpDiscoveredTool[];
  readonly error: string | null;
}
