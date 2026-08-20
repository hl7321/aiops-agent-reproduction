export type ChatMessageRole = "user" | "assistant" | "system" | "tool";
export type ChatMemoryMode = "every_30_turns" | "context_70_percent" | "manual";

export interface ChatReference {
  readonly chunkId: string;
  readonly documentId: string;
  readonly knowledgeBaseId: string;
  readonly source: string;
  readonly excerpt?: string;
}

export interface ChatMessageMetadata {
  readonly references?: readonly ChatReference[];
  readonly toolCallIds?: readonly string[];
}

export interface ChatMessage {
  readonly id: string;
  readonly sessionId: string;
  readonly role: ChatMessageRole;
  readonly content: string;
  readonly sequence: number;
  readonly metadata: ChatMessageMetadata;
  readonly createdAt: string;
}

export interface ChatSession {
  readonly id: string;
  readonly title: string;
  readonly memoryMode: ChatMemoryMode;
  readonly memorySummary: string | null;
  readonly contextTokens: number;
  readonly contextWindowTokens: number;
  readonly contextUsagePercent: number;
  readonly compactedMessageCount: number;
  readonly lastCompactedAt: string | null;
  readonly canCompact: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface UpdateChatMemoryRequest {
  readonly memoryMode: ChatMemoryMode;
}

export interface ChatSessionListData {
  readonly sessions: readonly ChatSession[];
}

export interface ChatSessionDetailData {
  readonly session: ChatSession;
  readonly messages: readonly ChatMessage[];
}

export interface AppendChatMessageRequest {
  readonly role: ChatMessageRole;
  readonly content: string;
  readonly metadata?: ChatMessageMetadata;
}

export interface ChatStreamMessageRequest {
  readonly content: string;
  readonly metadata?: ChatMessageMetadata;
}

export type AgentToolCallAuditStatus = "started" | "completed" | "failed";

export interface AgentToolCallAudit {
  readonly id: string;
  readonly toolCallId: string;
  readonly chatSessionId: string | null;
  readonly diagnosticTaskId: string | null;
  readonly toolName: string;
  readonly arguments: Readonly<Record<string, unknown>>;
  readonly status: AgentToolCallAuditStatus;
  readonly resultSummary: string | null;
  readonly errorMessage: string | null;
  readonly startedAt: string;
  readonly completedAt: string | null;
  readonly durationMs: number | null;
}

export interface AgentToolCallAuditListData {
  readonly items: readonly AgentToolCallAudit[];
}

export interface ChatDeleteData {
  readonly deleted: true;
  readonly sessionId: string;
}
