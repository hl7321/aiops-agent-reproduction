// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatConfigurationStore } from "../../stores/chatConfiguration";
import ChatConfigurationSidebar from "./ChatConfigurationSidebar.vue";

beforeEach(() => setActivePinia(createPinia()));

describe("ChatConfigurationSidebar", () => {
  it("提供 Prompt 单选/编辑和 Skill 多选/删除的真实 store 操作", async () => {
    const store = useChatConfigurationStore();
    store.prompts = [{ id: "prompt-1", label: "值班", content: "简洁", createdAt: "now", updatedAt: "now" }];
    store.skills = [{ id: "skill-1", name: "knowledge-search", description: "检索", filename: "SKILL.md", content: "body", metadata: {}, summary: "检索", createdAt: "now", updatedAt: "now" }];
    store.updateSelection = vi.fn(async () => undefined);
    store.updatePrompt = vi.fn(async () => undefined);
    store.uploadSkill = vi.fn(async () => undefined);
    store.deletePrompt = vi.fn(async () => undefined);
    store.deleteSkill = vi.fn(async () => undefined);
    const wrapper = mount(ChatConfigurationSidebar);

    await wrapper.get("select").setValue("prompt-1");
    expect(store.updateSelection).toHaveBeenCalledWith("prompt-1", []);
    await wrapper.get('.asset-list button').trigger("click");
    expect((wrapper.get('[aria-label="Prompt 名称"]').element as HTMLInputElement).value).toBe("值班");
    await wrapper.get('[aria-label="Prompt 内容"]').setValue("更新后的 Prompt");
    await wrapper.get(".asset-form").trigger("submit");
    expect(store.updatePrompt).toHaveBeenCalledWith("prompt-1", {
      label: "值班", content: "更新后的 Prompt",
    });
    await wrapper.get('input[type="checkbox"]').setValue(true);
    expect(store.updateSelection).toHaveBeenLastCalledWith(null, ["skill-1"]);
    const skillInput = wrapper.get('input[type="file"]');
    const skillFile = new File(["---\nname: knowledge-search\ndescription: 检索\n---\n"], "SKILL.md", { type: "text/markdown" });
    Object.defineProperty(skillInput.element, "files", { configurable: true, value: [skillFile] });
    await skillInput.trigger("change");
    expect(store.uploadSkill).toHaveBeenCalledOnce();
    const deleteButtons = wrapper.findAll(".asset-list button").filter((button) => button.text() === "删除");
    await deleteButtons[0]?.trigger("click");
    expect(store.deletePrompt).toHaveBeenCalledWith("prompt-1");
    await deleteButtons.at(-1)?.trigger("click");
    expect(store.deleteSkill).toHaveBeenCalledWith("skill-1");
  });
});
