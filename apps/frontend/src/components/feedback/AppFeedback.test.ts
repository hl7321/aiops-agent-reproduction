// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useFeedbackStore } from "../../stores/feedback";
import AppFeedback from "./AppFeedback.vue";

beforeEach(() => {
  vi.useFakeTimers();
  setActivePinia(createPinia());
});

afterEach(() => vi.useRealTimers());

describe("AppFeedback", () => {
  it("支持文字语义、手动关闭和 3 秒自动消失", async () => {
    const store = useFeedbackStore();
    const wrapper = mount(AppFeedback);
    store.show("success", "登录成功");
    await wrapper.vm.$nextTick();

    expect(wrapper.get('[role="status"]').text()).toContain("登录成功");
    await wrapper.get("button").trigger("click");
    expect(store.current).toBeNull();

    store.show("error", "登录失败");
    await vi.advanceTimersByTimeAsync(3_000);
    expect(store.current).toBeNull();
  });

  it("新消息重置 timer，unmount 会清理 timer", async () => {
    const clearSpy = vi.spyOn(globalThis, "clearTimeout");
    const store = useFeedbackStore();
    const wrapper = mount(AppFeedback);

    store.show("info", "第一条");
    await vi.advanceTimersByTimeAsync(2_000);
    store.show("success", "第二条");
    await vi.advanceTimersByTimeAsync(1_100);
    expect(store.current?.message).toBe("第二条");

    wrapper.unmount();
    expect(clearSpy).toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(3_000);
    expect(store.current?.message).toBe("第二条");
  });
});
