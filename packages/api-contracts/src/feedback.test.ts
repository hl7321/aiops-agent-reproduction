import { describe, expect, expectTypeOf, it } from "vitest";

import {
  FEEDBACK_OPENAPI_OPERATIONS,
  FEEDBACK_RATINGS,
  FEEDBACK_REASONS,
  FEEDBACK_TARGET_TYPES,
} from "./index";
import type { FeedbackListData, UserFeedback, UserFeedbackUpsertRequest } from "./index";

describe("用户反馈共享合同", () => {
  it("固定目标、评分和问题类型目录", () => {
    expect(FEEDBACK_TARGET_TYPES).toEqual([
      "chat_message", "citation", "diagnostic_step", "diagnostic_report",
    ]);
    expect(FEEDBACK_RATINGS).toEqual(["positive", "negative"]);
    expect(FEEDBACK_REASONS).toEqual([
      "incorrect", "incomplete", "irrelevant", "unclear", "unsafe", "other",
    ]);
  });

  it("subjectId 可空且 upsert 不接受 owner", () => {
    const request: UserFeedbackUpsertRequest = {
      targetType: "chat_message",
      targetId: "message-1",
      subjectId: null,
      rating: "positive",
      reason: null,
      comment: null,
      correction: null,
    };
    const item: UserFeedback = {
      id: "feedback-1",
      targetType: request.targetType,
      targetId: request.targetId,
      subjectId: request.subjectId ?? null,
      rating: request.rating,
      reason: request.reason ?? null,
      comment: request.comment ?? null,
      correction: request.correction ?? null,
      createdAt: "2026-08-21T00:00:00Z",
      updatedAt: "2026-08-21T00:00:00Z",
    };
    const data: FeedbackListData = { items: [item] };
    expect(data.items[0]?.subjectId).toBeNull();
    expect(request).not.toHaveProperty("ownerUserId");
    expectTypeOf(request.targetType).toMatchTypeOf<
      "chat_message" | "citation" | "diagnostic_step" | "diagnostic_report"
    >();
  });

  it("登记三条 bearer feedback operation", () => {
    expect(FEEDBACK_OPENAPI_OPERATIONS.map((item) => item.operationId)).toEqual([
      "listUserFeedback", "upsertUserFeedback", "deleteUserFeedback",
    ]);
    for (const operation of FEEDBACK_OPENAPI_OPERATIONS) {
      expect(operation.security).toEqual(["BearerAuth"]);
      expect(operation.errors).toEqual(expect.arrayContaining([
        "AUTH_REQUIRED", "AUTH_FORBIDDEN", "BUSINESS_RESOURCE_NOT_FOUND",
      ]));
    }
  });
});
