import { describe, expect, expectTypeOf, it } from "vitest";

import { ERROR_DEFINITIONS, MCP_OPENAPI_OPERATIONS } from "./index";
import type {
  CreateMcpConnectionRequest,
  McpConnection,
  McpConnectionCheckResult,
  McpDiscoveredTool,
  UpdateMcpConnectionRequest,
} from "./index";

describe("MCP 连接共享合同", () => {
  it("定义真实连接、工具快照和检查结果", () => {
    expectTypeOf<McpConnection["transport"]>().toEqualTypeOf<"sse" | "streamable_http">();
    expectTypeOf<McpConnection>().toHaveProperty("discoveredTools");
    expectTypeOf<McpDiscoveredTool>().toEqualTypeOf<{
      readonly name: string;
      readonly description: string | null;
    }>();
    expectTypeOf<McpConnectionCheckResult["status"]>().toEqualTypeOf<"connected" | "failed">();
    expectTypeOf<CreateMcpConnectionRequest>().toHaveProperty("timeoutSeconds");
    expectTypeOf<UpdateMcpConnectionRequest>().toHaveProperty("retries");
  });

  it("登记五个受 bearer 保护的 operation", () => {
    expect(MCP_OPENAPI_OPERATIONS.map((item) => item.operationId)).toEqual([
      "listMcpConnections",
      "createMcpConnection",
      "updateMcpConnection",
      "deleteMcpConnection",
      "checkMcpConnection",
    ]);
    expect(MCP_OPENAPI_OPERATIONS).toHaveLength(5);
    for (const operation of MCP_OPENAPI_OPERATIONS) {
      expect(operation.security).toEqual(["BearerAuth"]);
      expect(operation.errors).toEqual(expect.arrayContaining(["AUTH_REQUIRED", "AUTH_FORBIDDEN"]));
    }
  });

  it("公开稳定连接失败和工具冲突错误", () => {
    expect(ERROR_DEFINITIONS.SYSTEM_MCP_CONNECTION_FAILED).toMatchObject({
      category: "system",
      httpStatus: 502,
    });
    expect(ERROR_DEFINITIONS.BUSINESS_MCP_TOOL_NAME_CONFLICT).toMatchObject({
      category: "business",
      httpStatus: 409,
    });
  });
});
