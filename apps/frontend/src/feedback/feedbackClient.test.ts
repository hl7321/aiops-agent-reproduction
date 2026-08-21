import { describe, expect, it } from "vitest";

import type { ApiClient } from "../transport/apiClient";
import { createUserFeedbackClient } from "./feedbackClient";

describe("feedbackClient", () => {
  it("使用 typed envelope 调用 list/upsert/delete 且不发送 owner", async () => {
    const calls: Array<readonly [string, RequestInit | undefined]> = [];
    const api: ApiClient = {
      async request<T>(input: string, init?: RequestInit) {
        calls.push([input, init]);
        return { data: {} as T, requestId: "req-1" };
      },
    };
    const client = createUserFeedbackClient(api);
    await client.list("citation", "message/1");
    await client.upsert({
      targetType: "citation", targetId: "message/1", subjectId: "chunk-1",
      rating: "negative", reason: "incorrect", comment: "错了", correction: "应为 X",
    });
    await client.delete("feedback/1");
    expect(calls[0]?.[0]).toBe(
      "/feedback?targetType=citation&targetId=message%2F1",
    );
    expect(calls[1]?.[1]).toMatchObject({ method: "POST" });
    expect(String(calls[1]?.[1]?.body)).not.toContain("owner");
    expect(calls[2]?.[0]).toBe("/feedback/feedback%2F1");
  });
});
