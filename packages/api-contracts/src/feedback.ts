export const FEEDBACK_TARGET_TYPES = [
  "chat_message",
  "citation",
  "diagnostic_step",
  "diagnostic_report",
] as const;
export type FeedbackTargetType = (typeof FEEDBACK_TARGET_TYPES)[number];

export const FEEDBACK_RATINGS = ["positive", "negative"] as const;
export type FeedbackRating = (typeof FEEDBACK_RATINGS)[number];

export const FEEDBACK_REASONS = [
  "incorrect",
  "incomplete",
  "irrelevant",
  "unclear",
  "unsafe",
  "other",
] as const;
export type FeedbackReason = (typeof FEEDBACK_REASONS)[number];

export interface UserFeedback {
  readonly id: string;
  readonly targetType: FeedbackTargetType;
  readonly targetId: string;
  readonly subjectId: string | null;
  readonly rating: FeedbackRating;
  readonly reason: FeedbackReason | null;
  readonly comment: string | null;
  readonly correction: string | null;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface FeedbackListQuery {
  readonly targetType: FeedbackTargetType;
  readonly targetId: string;
}

export interface FeedbackListData { readonly items: readonly UserFeedback[]; }

export interface UserFeedbackUpsertRequest {
  readonly targetType: FeedbackTargetType;
  readonly targetId: string;
  readonly subjectId?: string | null;
  readonly rating: FeedbackRating;
  readonly reason?: FeedbackReason | null;
  readonly comment?: string | null;
  readonly correction?: string | null;
}

export interface FeedbackDeleteData {
  readonly deleted: true;
  readonly feedbackId: string;
}
