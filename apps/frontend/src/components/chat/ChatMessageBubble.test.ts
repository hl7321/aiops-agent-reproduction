// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@super-ai/api-contracts";

import ChatMessageBubble from "./ChatMessageBubble.vue";

const message: ChatMessage = {
  id: "message-1", sessionId: "session-1", role: "assistant", content: "回答",
  sequence: 2, createdAt: "now", metadata: { references: [{
    chunkId: "chunk-1", documentId: "doc-1", knowledgeBaseId: "kb-1",
    source: "runbook.md", excerpt: "步骤", metadata: {}, vectorRank: 1,
    vectorScore: 0.9, bm25Rank: null, bm25Score: null, rrfScore: 0.01,
    rerankRank: 1, rerankScore: 0.9, score: 0.9,
  }] },
};

describe("ChatMessageBubble 反馈接入", () => {
  it("持久 assistant answer 与 citation 各有独立反馈目标", () => {
    const wrapper = mount(ChatMessageBubble, {
      props: { message },
      global: {
        plugins: [createPinia()],
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
          UserFeedbackControl: {
            props: ["targetType", "targetId", "subjectId"],
            template: '<i class="feedback-target" :data-type="targetType" :data-target="targetId" :data-subject="subjectId" />',
          },
        },
      },
    });
    const controls = wrapper.findAll(".feedback-target");
    expect(controls).toHaveLength(2);
    expect(controls.map((item) => item.attributes("data-type"))).toEqual([
      "citation", "chat_message",
    ]);
    expect(controls[0]?.attributes("data-target")).toBe("message-1");
    expect(controls[0]?.attributes("data-subject")).toBe("chunk-1");
  });

  it("流式临时 assistant 不展示反馈控件", () => {
    const wrapper = mount(ChatMessageBubble, {
      props: { message: { ...message, id: "live-assistant" }, feedbackEnabled: false },
      global: {
        plugins: [createPinia()],
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
          UserFeedbackControl: { template: '<i class="feedback-target" />' },
        },
      },
    });
    expect(wrapper.find(".feedback-target").exists()).toBe(false);
  });
});
