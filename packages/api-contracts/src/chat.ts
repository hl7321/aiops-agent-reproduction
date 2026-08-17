export type ChatMessageRole = "user" | "assistant" | "system" | "tool";

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
  readonly createdAt: string;
  readonly updatedAt: string;
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

export interface ChatDeleteData {
  readonly deleted: true;
  readonly sessionId: string;
}
