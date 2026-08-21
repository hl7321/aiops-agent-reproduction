// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { describe, expect, it, vi } from "vitest";

import type { UserFeedback } from "@super-ai/api-contracts";

import UserFeedbackControl from "./UserFeedbackControl.vue";

describe("UserFeedbackControl", () => {
  it("支持赞同、问题类型、评论、纠正和更新", async () => {
    const save = vi.fn(async () => undefined);
    const wrapper = mount(UserFeedbackControl, {
      props: {
        targetType: "chat_message", targetId: "message-1", subjectId: null,
        load: async () => undefined, save, remove: async () => undefined,
      },
      global: { plugins: [createPinia()] },
    });
    await vi.waitFor(() => expect(wrapper.find('[aria-label="反对"]').exists()).toBe(true));
    await wrapper.get('[aria-label="反对"]').trigger("click");
    await wrapper.get("select").setValue("incorrect");
    await wrapper.get('[name="feedback-comment"]').setValue("答案有误");
    await wrapper.get('[name="feedback-correction"]').setValue("应为 X");
    await wrapper.get("form").trigger("submit");
    expect(save).toHaveBeenCalledWith(expect.objectContaining({
      rating: "negative", reason: "incorrect", comment: "答案有误", correction: "应为 X",
    }));
  });

  it("提交失败保留草稿并显示错误", async () => {
    const wrapper = mount(UserFeedbackControl, {
      props: {
        targetType: "diagnostic_report", targetId: "report-1", subjectId: null,
        load: async () => undefined,
        save: async () => { throw new Error("保存失败"); },
        remove: async () => undefined,
      },
      global: { plugins: [createPinia()] },
    });
    await vi.waitFor(() => expect(wrapper.find('[aria-label="赞同"]').exists()).toBe(true));
    await wrapper.get('[aria-label="赞同"]').trigger("click");
    await wrapper.get('[name="feedback-comment"]').setValue("保留我");
    await wrapper.get("form").trigger("submit");
    expect(wrapper.get('[role="alert"]').text()).toContain("保存失败");
    expect((wrapper.get('[name="feedback-comment"]').element as HTMLTextAreaElement).value).toBe("保留我");
  });

  it("恢复已有反馈并可删除", async () => {
    const existing: UserFeedback = {
      id: "f-1", targetType: "diagnostic_step", targetId: "step-1", subjectId: null,
      rating: "negative", reason: "unclear", comment: "不清楚", correction: null,
      createdAt: "now", updatedAt: "now",
    };
    const remove = vi.fn(async () => undefined);
    const wrapper = mount(UserFeedbackControl, {
      props: {
        targetType: "diagnostic_step", targetId: "step-1", subjectId: null,
        load: async () => existing, save: async () => undefined, remove,
      },
      global: { plugins: [createPinia()] },
    });
    await vi.waitFor(() => expect(wrapper.text()).toContain("删除反馈"));
    await wrapper.get('[data-action="delete-feedback"]').trigger("click");
    expect(remove).toHaveBeenCalledWith(existing);
  });
});
