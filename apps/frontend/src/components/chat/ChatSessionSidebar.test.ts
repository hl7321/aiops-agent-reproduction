// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatStore } from "../../stores/chat";
import ChatSessionSidebar from "./ChatSessionSidebar.vue";

beforeEach(() => setActivePinia(createPinia()));

describe("ChatSessionSidebar", () => {
  it("使用全局左栏执行新建、切换和确认删除", async () => {
    const store = useChatStore();
    const session = {
      id: "session-1", title: "排障会话", memoryMode: "manual" as const,
      memorySummary: null, contextTokens: 0, contextWindowTokens: 1000,
      contextUsagePercent: 0, compactedMessageCount: 0, lastCompactedAt: null,
      canCompact: false, createdAt: "now", updatedAt: "now",
    };
    store.sessions = [session];
    store.selectedDetail = { session, messages: [] };
    store.createSession = vi.fn(async () => undefined);
    store.selectSession = vi.fn(async () => undefined);
    store.deleteSession = vi.fn(async () => undefined);
    store.ensureActiveSession = vi.fn(async () => undefined);
    const wrapper = mount(ChatSessionSidebar);

    await wrapper.get('[aria-label="新建会话"]').trigger("click");
    await wrapper.get(".conversation-list__item").trigger("click");
    expect(store.createSession).toHaveBeenCalledOnce();
    expect(store.selectSession).toHaveBeenCalledWith("session-1");

    await wrapper.get(".conversation-delete").trigger("click");
    expect(wrapper.get('[role="dialog"]').text()).toContain("确定继续");
    await wrapper.get('[role="dialog"] button:last-child').trigger("click");
    expect(store.deleteSession).toHaveBeenCalledWith("session-1");
  });
});
