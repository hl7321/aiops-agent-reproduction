import type {
  FeedbackDeleteData,
  FeedbackListData,
  FeedbackTargetType,
  UserFeedback,
  UserFeedbackUpsertRequest,
} from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";

export interface UserFeedbackClient {
  list(targetType: FeedbackTargetType, targetId: string): Promise<ApiResult<FeedbackListData>>;
  upsert(body: UserFeedbackUpsertRequest): Promise<ApiResult<UserFeedback>>;
  delete(id: string): Promise<ApiResult<FeedbackDeleteData>>;
}

export function createUserFeedbackClient(api: ApiClient): UserFeedbackClient {
  return {
    list: (targetType, targetId) => api.request<FeedbackListData>(
      `/feedback?targetType=${encodeURIComponent(targetType)}&targetId=${encodeURIComponent(targetId)}`,
    ),
    upsert: (body) => api.request<UserFeedback>("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    delete: (id) => api.request<FeedbackDeleteData>(
      `/feedback/${encodeURIComponent(id)}`, { method: "DELETE" },
    ),
  };
}
