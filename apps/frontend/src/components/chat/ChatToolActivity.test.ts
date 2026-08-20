// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ChatToolActivity from "./ChatToolActivity.vue";

describe("ChatToolActivity", () => {
  it("折叠展示真实 reasoning 与安全摘要，但不渲染原始工具输入输出", () => {
    const wrapper = mount(ChatToolActivity, { props: {
      reasoning: "模型真实推理片段",
      liveToolCalls: {
        "call-1": {
          toolCallId: "call-1", toolName: "knowledge_retrieval", lifecycle: "completed",
          input: { query: "不得展示的查询" }, output: { secret: "不得展示的结果" },
        },
      },
      audits: [{
        id: "audit-1", toolCallId: "call-1", chatSessionId: "session-1",
        diagnosticTaskId: null, toolName: "knowledge_retrieval",
        arguments: { query: "不得展示的审计参数" }, status: "completed",
        resultSummary: "安全摘要", errorMessage: null, startedAt: "now",
        completedAt: "later", durationMs: 10,
      }],
    } });
    expect(wrapper.text()).toContain("模型真实推理片段");
    expect(wrapper.text()).toContain("安全摘要");
    expect(wrapper.text()).not.toContain("不得展示");
    expect(wrapper.findAll("details")).toHaveLength(2);
  });
});
