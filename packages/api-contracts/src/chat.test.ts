import { describe, expect, expectTypeOf, it } from "vitest";

import manifest from "../contract-manifest.json";
import { CHAT_OPENAPI_OPERATIONS, OPENAPI_PATHS } from "./index";
import type {
  AgentToolCallAudit,
  AgentToolCallAuditListData,
  AppendChatMessageRequest,
  ChatDeleteData,
  ChatMessage,
  ChatMessageMetadata,
  ChatMessageRole,
  ChatMemoryMode,
  ChatReference,
  ChatSession,
  ChatSessionDetailData,
  ChatSessionListData,
  ChatStreamMessageRequest,
  UpdateChatMemoryRequest,
} from "./index";

describe("聊天会话共享合同", () => {
  it("表达会话、消息、role 和结构化 metadata", () => {
    const role: ChatMessageRole = "tool";
    const reference: ChatReference = {
      chunkId: "chunk-1",
      documentId: "doc-1",
      knowledgeBaseId: "kb-1",
      source: "runbook.md",
      excerpt: "处理步骤",
      metadata: { heading: "处置" },
      vectorRank: 1,
      vectorScore: 0.91,
      bm25Rank: null,
      bm25Score: null,
      rrfScore: 0.0164,
      rerankRank: 1,
      rerankScore: 0.97,
      score: 0.97,
    };
    const metadata: ChatMessageMetadata = {
      references: [reference],
      toolCallIds: ["call-1"],
    };
    const message: ChatMessage = {
      id: "message-1",
      sessionId: "session-1",
      role,
      content: "执行工具",
      sequence: 1,
      metadata,
      createdAt: "2026-08-17T00:00:00Z",
    };
    const session: ChatSession = {
      id: "session-1",
      title: "新会话",
      memoryMode: "context_70_percent",
      memorySummary: null,
      contextTokens: 140,
      contextWindowTokens: 1000,
      contextUsagePercent: 14,
      compactedMessageCount: 0,
      lastCompactedAt: null,
      canCompact: true,
      createdAt: "2026-08-17T00:00:00Z",
      updatedAt: "2026-08-17T00:00:00Z",
    };
    const list: ChatSessionListData = { sessions: [session] };
    const detail: ChatSessionDetailData = { session, messages: [message] };
    const append: AppendChatMessageRequest = { role: "user", content: "你好", metadata: {} };
    const deleted: ChatDeleteData = { deleted: true, sessionId: session.id };

    expect(["user", "assistant", "system", "tool"] satisfies ChatMessageRole[]).toContain(role);
    expect(detail.messages[0]?.metadata).toEqual(metadata);
    expect(list.sessions).toEqual([session]);
    expect(append.content).toBe("你好");
    expect(deleted).toEqual({ deleted: true, sessionId: "session-1" });
    expectTypeOf(message.sequence).toEqualTypeOf<number>();
    expect(session.contextUsagePercent).toBe(14);
  });

  it("表达三种记忆模式与更新请求", () => {
    const modes: readonly ChatMemoryMode[] = [
      "every_30_turns", "context_70_percent", "manual",
    ];
    const request: UpdateChatMemoryRequest = { memoryMode: "manual" };

    expect(modes).toEqual(["every_30_turns", "context_70_percent", "manual"]);
    expect(request).toEqual({ memoryMode: "manual" });
  });

  it("表达只允许 user 内容的流请求和排他父对象审计", () => {
    const streamRequest: ChatStreamMessageRequest = {
      content: "请检查订单服务告警",
      metadata: { toolCallIds: [] },
    };
    const audit: AgentToolCallAudit = {
      id: "audit-1",
      toolCallId: "call-1",
      chatSessionId: "session-1",
      diagnosticTaskId: null,
      toolName: "knowledge_retrieval",
      arguments: { query: "订单服务" },
      status: "completed",
      resultSummary: "返回 1 条引用",
      errorMessage: null,
      startedAt: "2026-08-17T00:00:00Z",
      completedAt: "2026-08-17T00:00:01Z",
      durationMs: 1000,
    };
    const list: AgentToolCallAuditListData = { items: [audit] };

    expect(streamRequest).not.toHaveProperty("role");
    expect(list.items[0]).toEqual(audit);
    expect(audit.chatSessionId === null).not.toBe(audit.diagnosticTaskId === null);
    expect(audit).not.toHaveProperty("parentCallId");
  });

  it("登记十种受保护聊天操作和记忆错误", () => {
    expect(CHAT_OPENAPI_OPERATIONS).toEqual(manifest.openapi.chatOperations);
    expect(CHAT_OPENAPI_OPERATIONS.map((operation) => operation.operationId)).toEqual([
      "createChatSession",
      "listChatSessions",
      "getChatSession",
      "appendChatMessage",
      "clearChatMessages",
      "deleteChatSession",
      "streamChatMessage",
      "listAgentToolCallAudits",
      "updateChatMemory",
      "compactChatMemory",
    ]);

    for (const operation of CHAT_OPENAPI_OPERATIONS) {
      expect(operation.security).toEqual(["BearerAuth"]);
      expect(operation.errors).toEqual(expect.arrayContaining(["AUTH_REQUIRED", "AUTH_FORBIDDEN"]));
      expect(operation.successData.length).toBeGreaterThan(0);
    }
    expect(CHAT_OPENAPI_OPERATIONS.find((item) => item.operationId === "appendChatMessage")?.errors)
      .toContain("VALIDATION_REQUEST_INVALID");
    expect(CHAT_OPENAPI_OPERATIONS.find((item) => item.operationId === "streamChatMessage")?.errors)
      .toContain("VALIDATION_REQUEST_INVALID");
    expect(OPENAPI_PATHS["/chat/sessions/{id}/messages:stream"].successData)
      .toBe("SseEventStream");
    expect(OPENAPI_PATHS["/chat/sessions/{id}/tool-call-audits"].successData)
      .toBe("AgentToolCallAuditListData");
    expect(OPENAPI_PATHS["/chat/sessions/{id}/memory"].method).toBe("PUT");
    expect(OPENAPI_PATHS["/chat/sessions/{id}/memory:compact"].method).toBe("POST");
    expect(CHAT_OPENAPI_OPERATIONS.find((item) => item.operationId === "streamChatMessage")?.errors)
      .toContain("CHAT_CONTEXT_LIMIT_REACHED");
    expect(OPENAPI_PATHS["/chat/sessions"].operationId).toBe("createChatSession");
  });
});
