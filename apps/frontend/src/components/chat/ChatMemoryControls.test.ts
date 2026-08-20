// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import type { ChatSession } from "@super-ai/api-contracts";

import ChatMemoryControls from "./ChatMemoryControls.vue";

const session: ChatSession = {
  id: "session-1", title: "会话", memoryMode: "context_70_percent", memorySummary: null,
  contextTokens: 700, contextWindowTokens: 1000, contextUsagePercent: 70,
  compactedMessageCount: 2, lastCompactedAt: null, canCompact: true,
  createdAt: "now", updatedAt: "now",
};

describe("ChatMemoryControls", () => {
  it("可更新模式并手动压缩", async () => {
    const onUpdate = vi.fn(async () => undefined);
    const onCompact = vi.fn(async () => undefined);
    const wrapper = mount(ChatMemoryControls, { props: { session, onUpdate, onCompact } });
    await wrapper.get("select").setValue("manual");
    await wrapper.get("button").trigger("click");
    expect(onUpdate).toHaveBeenCalledWith("manual");
    expect(onCompact).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("70.0%");
  });

  it("操作失败后展示可恢复错误", async () => {
    const wrapper = mount(ChatMemoryControls, { props: {
      session,
      onUpdate: vi.fn(async () => { throw new Error("压缩配置失败"); }),
      onCompact: vi.fn(async () => undefined),
    } });
    await wrapper.get("select").setValue("manual");
    expect(wrapper.get('[role="alert"]').text()).toContain("压缩配置失败");
  });
});
