import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { UserFeedback } from "@super-ai/api-contracts";

import type { UserFeedbackClient } from "../feedback/feedbackClient";
import { createUserFeedbackStore } from "./userFeedback";

const item: UserFeedback = {
  id: "feedback-1", targetType: "chat_message", targetId: "message-1", subjectId: null,
  rating: "positive", reason: null, comment: "很好", correction: null,
  createdAt: "2026-08-21T00:00:00Z", updatedAt: "2026-08-21T00:00:00Z",
};

function client(): UserFeedbackClient {
  return {
    list: vi.fn(async () => ({ data: { items: [item] }, requestId: "r1" })),
    upsert: vi.fn(async (body) => ({ data: { ...item, ...body }, requestId: "r2" })),
    delete: vi.fn(async (id) => ({ data: { deleted: true as const, feedbackId: id }, requestId: "r3" })),
  };
}

describe("userFeedback store", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("从服务器恢复并只在成功响应后更新", async () => {
    const store = createUserFeedbackStore({ client: client() })();
    await store.load("chat_message", "message-1");
    expect(store.find("chat_message", "message-1", null)?.comment).toBe("很好");
    await store.save({ ...item, rating: "negative", comment: "需要改进" });
    expect(store.find("chat_message", "message-1", null)?.rating).toBe("negative");
  });

  it("失败不覆盖服务器旧值并保留可重试错误", async () => {
    const fake = client();
    fake.upsert = vi.fn(async () => { throw new Error("network failed"); });
    const store = createUserFeedbackStore({ client: fake })();
    await store.load("chat_message", "message-1");
    await expect(store.save({ ...item, rating: "negative" })).rejects.toThrow("network failed");
    expect(store.find("chat_message", "message-1", null)?.rating).toBe("positive");
    expect(store.errorFor("chat_message", "message-1", null)).toBe("network failed");
  });

  it("删除失败保留记录，reset 清理受保护内存", async () => {
    const fake = client();
    fake.delete = vi.fn(async () => { throw new Error("delete failed"); });
    const store = createUserFeedbackStore({ client: fake })();
    await store.load("chat_message", "message-1");
    await expect(store.remove(item)).rejects.toThrow("delete failed");
    expect(store.find("chat_message", "message-1", null)).toEqual(item);
    store.reset();
    expect(store.find("chat_message", "message-1", null)).toBeUndefined();
  });
});
