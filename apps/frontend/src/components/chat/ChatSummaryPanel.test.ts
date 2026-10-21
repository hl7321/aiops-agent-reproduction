// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import type { ChatSession } from "@super-ai/api-contracts";

import ChatSummaryPanel from "./ChatSummaryPanel.vue";

const SUMMARY_TEXT = "用户要求记住编号1至30，助手均已确认。";

const compressed: ChatSession = {
  id: "session-compressed",
  title: "30 轮演示",
  memoryMode: "every_30_turns",
  memorySummary: SUMMARY_TEXT,
  contextTokens: 87,
  contextWindowTokens: 1_048_576,
  contextUsagePercent: 0.01,
  compactedMessageCount: 60,
  lastCompactedAt: "2026-10-21T10:08:02Z",
  canCompact: true,
  createdAt: "now",
  updatedAt: "now",
};

const fresh: ChatSession = {
  ...compressed,
  id: "session-fresh",
  title: "新会话",
  memorySummary: null,
  compactedMessageCount: 0,
  lastCompactedAt: null,
};

describe("ChatSummaryPanel", () => {
  it("列出会话压缩状态并展示选中摘要", () => {
    const wrapper = mount(ChatSummaryPanel, {
      props: {
        sessions: [compressed, fresh],
        selectedSessionId: compressed.id,
        onSelect: vi.fn(async () => undefined),
      },
    });

    const text = wrapper.text();
    expect(text).toContain("30 轮演示");
    expect(text).toContain("已压缩 60 条");
    expect(text).toContain("新会话");
    expect(text).toContain("未压缩");
    expect(text).toContain(SUMMARY_TEXT);
    expect(text).toContain("每 30 轮压缩");
    expect(text).toContain("60 条");
  });

  it("点击会话触发选择，切换后展示空状态或新摘要", async () => {
    const onSelect = vi.fn(async () => undefined);
    const wrapper = mount(ChatSummaryPanel, {
      props: {
        sessions: [compressed, fresh],
        selectedSessionId: compressed.id,
        onSelect,
      },
    });

    await wrapper.findAll(".summary-session")[1]?.trigger("click");
    expect(onSelect).toHaveBeenCalledWith(fresh.id);

    await wrapper.setProps({ selectedSessionId: fresh.id });
    expect(wrapper.text()).toContain("尚未压缩");

    await wrapper.setProps({
      selectedSessionId: compressed.id,
      sessions: [{ ...compressed, memorySummary: "更新后的摘要" }],
    });
    expect(wrapper.text()).toContain("更新后的摘要");
  });

  it("选择失败时显示可重试错误", async () => {
    const wrapper = mount(ChatSummaryPanel, {
      props: {
        sessions: [compressed],
        selectedSessionId: compressed.id,
        onSelect: vi.fn(async () => {
          throw new Error("切换失败");
        }),
      },
    });

    await wrapper.get(".summary-session").trigger("click");
    expect(wrapper.get('[role="alert"]').text()).toContain("切换失败");
  });
});
