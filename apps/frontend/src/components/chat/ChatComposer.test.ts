// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import "../../styles/global.css";
import ChatComposer from "./ChatComposer.vue";

describe("ChatComposer", () => {
  it("桌面主区保持局部滚动、固定 composer 且 textarea 禁止 resize", () => {
    const wrapper = mount(ChatComposer, { props: { onSend: vi.fn(async () => undefined) } });
    const textarea = wrapper.get("textarea").element;
    expect(textarea.getAttribute("style")).toContain("resize: none");
    expect(wrapper.get("form").classes()).toContain("chat-composer");
  });
  it("Enter 发送、Shift+Enter 换行且 IME composing 不误发", async () => {
    const onSend = vi.fn(async () => undefined);
    const wrapper = mount(ChatComposer, { props: { onSend } });
    const textarea = wrapper.get("textarea");
    await textarea.setValue("中文问题");

    await textarea.trigger("compositionstart");
    await textarea.trigger("keydown", { key: "Enter", isComposing: true });
    await textarea.trigger("compositionend");
    await textarea.trigger("keydown", { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();

    await textarea.trigger("keydown", { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("中文问题");
  });

  it("发送失败保留草稿供恢复", async () => {
    const wrapper = mount(ChatComposer, {
      props: { onSend: vi.fn(async () => { throw new Error("网络失败"); }) },
    });
    await wrapper.get("textarea").setValue("不要丢失");
    await wrapper.get("form").trigger("submit");
    expect((wrapper.get("textarea").element as HTMLTextAreaElement).value).toBe("不要丢失");
    expect(wrapper.get('[role="alert"]').text()).toContain("网络失败");
  });
});
