export type DocumentIndexStatus =
  | "pending" | "running" | "succeeded" | "failed" | "cancelled";

export interface DocumentIndexTask {
  readonly id: string;
  readonly knowledgeBaseId: string;
  readonly documentId: string;
  readonly status: DocumentIndexStatus;
  readonly failureReason?: string | null;
  readonly retryOfTaskId?: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly startedAt?: string | null;
  readonly completedAt?: string | null;
}
