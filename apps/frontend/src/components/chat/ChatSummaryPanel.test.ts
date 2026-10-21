// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import type { ChatSession } from "@super-ai/api-contracts";

import ChatSummaryPanel from "./ChatSummaryPanel.vue";

const STRUCTURED_SUMMARY = [
  "## 对话目标",
  "- 排查订单告警",
  "## 关键事实与标识",
  "- incident_id: java-ecom-007",
  "## 已做决定",
  "- 先查广州日志",
  "## 工具与证据",
  "- SearchLog 命中 4 条",
  "## 未解决事项",
  "- 等待人工确认",
  "## 风险与注意事项",
  "- 不要自动重启服务",
].join("\n");

const compressed: ChatSession = {
  id: "session-compressed",
  title: "30 轮演示",
  memoryMode: "every_30_turns",
  memorySummary: STRUCTURED_SUMMARY,
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

const legacy: ChatSession = {
  ...compressed,
  id: "session-legacy",
  title: "旧摘要",
  memorySummary: "用户询问助手功能与上下文窗口大小。",
  compactedMessageCount: 4,
};

function mountPanel(onSelect = vi.fn(async () => undefined)) {
  return mount(ChatSummaryPanel, {
    props: {
      sessions: [compressed, fresh, legacy],
      selectedSessionId: compressed.id,
      onSelect,
    },
  });
}

describe("ChatSummaryPanel", () => {
  it("列出压缩状态，默认不展开摘要", () => {
    const wrapper = mountPanel();

    const text = wrapper.text();
    expect(text).toContain("已压缩 60 条");
    expect(text).toContain("未压缩");
    expect(text).not.toContain("排查订单告警");
    expect(wrapper.find(".summary-card").exists()).toBe(false);
  });

  it("点击会话就地展开六段卡片，再点收起", async () => {
    const wrapper = mountPanel();

    await wrapper.findAll(".summary-session")[0]?.trigger("click");
    expect(wrapper.findAll(".summary-card")).toHaveLength(1);
    for (const heading of [
      "对话目标",
      "关键事实与标识",
      "已做决定",
      "工具与证据",
      "未解决事项",
      "风险与注意事项",
    ]) {
      expect(wrapper.text()).toContain(heading);
    }

    await wrapper.get(".summary-card__head button").trigger("click");
    expect(wrapper.find(".summary-card").exists()).toBe(false);
  });

  it("切换会话展示空状态或旧摘要，且同一时间只有一张卡片", async () => {
    const onSelect = vi.fn(async () => undefined);
    const wrapper = mountPanel(onSelect);

    await wrapper.findAll(".summary-session")[1]?.trigger("click");
    expect(onSelect).toHaveBeenCalledWith(fresh.id);
    expect(wrapper.text()).toContain("尚未压缩");

    await wrapper.setProps({ selectedSessionId: legacy.id });
    await wrapper.findAll(".summary-session")[2]?.trigger("click");
    expect(wrapper.text()).toContain("旧摘要");
    expect(wrapper.findAll(".summary-card")).toHaveLength(1);
  });

  it("选择失败时显示可重试错误", async () => {
    const wrapper = mountPanel(
      vi.fn(async () => {
        throw new Error("切换失败");
      }),
    );

    await wrapper.findAll(".summary-session")[1]?.trigger("click");
    expect(wrapper.get('[role="alert"]').text()).toContain("切换失败");
  });
});
