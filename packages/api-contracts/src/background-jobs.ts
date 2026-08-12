export type BackgroundJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface BackgroundJob {
  readonly id: string;
  readonly ownerUserId: string;
  readonly kind: string;
  readonly resourceType?: string;
  readonly resourceId?: string;
  readonly status: BackgroundJobStatus;
  readonly payload: unknown;
  readonly attempt: number;
  readonly maxAttempts: number;
  readonly timeoutSeconds: number;
  readonly availableAt: string;
  readonly leaseOwner?: string;
  readonly leaseExpiresAt?: string;
  readonly cancelRequestedAt?: string;
  readonly retryOfJobId?: string;
  readonly errorMessage?: string;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly startedAt?: string;
  readonly completedAt?: string;
}

export interface BackgroundJobEvent {
  readonly sequence: number;
  readonly jobId: string;
  readonly ownerUserId: string;
  readonly type: BackgroundJobStatus;
  readonly data: unknown;
  readonly createdAt: string;
}

export interface BackgroundJobListData {
  readonly items: readonly BackgroundJob[];
}
