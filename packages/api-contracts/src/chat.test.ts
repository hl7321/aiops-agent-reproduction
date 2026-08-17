import { describe, expect, expectTypeOf, it } from "vitest";

import manifest from "../contract-manifest.json";
import { CHAT_OPENAPI_OPERATIONS, OPENAPI_PATHS } from "./index";
import type {
  AppendChatMessageRequest,
  ChatDeleteData,
  ChatMessage,
  ChatMessageMetadata,
  ChatMessageRole,
  ChatReference,
  ChatSession,
  ChatSessionDetailData,
  ChatSessionListData,
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
  });

  it("登记六种受保护聊天操作和 append 验证错误", () => {
    expect(CHAT_OPENAPI_OPERATIONS).toEqual(manifest.openapi.chatOperations);
    expect(CHAT_OPENAPI_OPERATIONS.map((operation) => operation.operationId)).toEqual([
      "createChatSession",
      "listChatSessions",
      "getChatSession",
      "appendChatMessage",
      "clearChatMessages",
      "deleteChatSession",
    ]);

    for (const operation of CHAT_OPENAPI_OPERATIONS) {
      expect(operation.security).toEqual(["BearerAuth"]);
      expect(operation.errors).toEqual(expect.arrayContaining(["AUTH_REQUIRED", "AUTH_FORBIDDEN"]));
      expect(operation.successData.length).toBeGreaterThan(0);
    }
    expect(CHAT_OPENAPI_OPERATIONS.find((item) => item.operationId === "appendChatMessage")?.errors)
      .toContain("VALIDATION_REQUEST_INVALID");
    expect(OPENAPI_PATHS["/chat/sessions"].operationId).toBe("createChatSession");
  });
});
