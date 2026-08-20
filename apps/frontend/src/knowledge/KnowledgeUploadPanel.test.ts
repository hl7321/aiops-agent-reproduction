// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import { KNOWLEDGE_UPLOAD_POLICY } from "@super-ai/api-contracts";

import KnowledgeUploadPanel from "./KnowledgeUploadPanel.vue";

function chooseFile(wrapper: ReturnType<typeof mount>, file: File): Promise<void> {
  const input = wrapper.get<HTMLInputElement>('input[type="file"]');
  Object.defineProperty(input.element, "files", { configurable: true, value: [file] });
  return input.trigger("change");
}

describe("KnowledgeUploadPanel", () => {
  it("从共享 policy 暴露 md/pdf accept 并让非固定策略不发送长度字段", async () => {
    const wrapper = mount(KnowledgeUploadPanel, { props: { busy: false } });
    expect(wrapper.get('input[type="file"]').attributes("accept")).toBe(".md,.pdf");
    await chooseFile(wrapper, new File(["# 标题"], "runbook.md", { type: "text/markdown" }));
    await wrapper.get("select").setValue("paragraph");
    expect(wrapper.find('input[name="maxCharacters"]').exists()).toBe(false);

    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("upload")?.[0]).toEqual([
      expect.any(File),
      { strategy: "paragraph" },
    ]);
  });

  it("fixed-character 显示参数并在 overlap 非法时阻止上传", async () => {
    const wrapper = mount(KnowledgeUploadPanel, { props: { busy: false } });
    await chooseFile(wrapper, new File(["正文"], "runbook.md", { type: "text/markdown" }));
    await wrapper.get("select").setValue("fixed-character");
    await wrapper.get('input[name="maxCharacters"]').setValue("100");
    await wrapper.get('input[name="overlap"]').setValue("100");

    await wrapper.get("form").trigger("submit");

    expect(wrapper.get('[role="alert"]').text()).toContain("重叠长度必须小于分段长度");
    expect(wrapper.emitted("upload")).toBeUndefined();
  });

  it("即时拒绝超出共享大小或非 md/pdf 的文件", async () => {
    const wrapper = mount(KnowledgeUploadPanel, { props: { busy: false } });
    await chooseFile(wrapper, new File(["x"], "notes.txt", { type: "text/plain" }));
    expect(wrapper.get('[role="alert"]').text()).toContain("只支持 Markdown 与 PDF");

    const oversized = new File(["x"], "large.pdf", { type: "application/pdf" });
    Object.defineProperty(oversized, "size", { value: KNOWLEDGE_UPLOAD_POLICY.maxBytes + 1 });
    await chooseFile(wrapper, oversized);
    expect(wrapper.get('[role="alert"]').text()).toContain("不能超过 10 MiB");
  });

  it("扩展名受信但浏览器未提供 MIME 时按共享 policy 补齐类型", async () => {
    const wrapper = mount(KnowledgeUploadPanel, { props: { busy: false } });
    await chooseFile(wrapper, new File(["# 标题"], "runbook.md"));
    await wrapper.get("select").setValue("paragraph");

    await wrapper.get("form").trigger("submit");

    const emittedFile = wrapper.emitted("upload")?.[0]?.[0] as File;
    expect(emittedFile.name).toBe("runbook.md");
    expect(emittedFile.type).toBe("text/markdown");
  });

  it("浏览器只提供通用二进制 MIME 时按 allowlist 扩展名补齐类型", async () => {
    const wrapper = mount(KnowledgeUploadPanel, { props: { busy: false } });
    await chooseFile(wrapper, new File(["# 标题"], "runbook.md", {
      type: "application/octet-stream",
    }));
    await wrapper.get("select").setValue("paragraph");

    await wrapper.get("form").trigger("submit");

    const emittedFile = wrapper.emitted("upload")?.[0]?.[0] as File;
    expect(emittedFile.type).toBe("text/markdown");
  });

  it("兼容浏览器的 text/x-markdown 别名并规范化为共享 MIME", async () => {
    const wrapper = mount(KnowledgeUploadPanel, { props: { busy: false } });
    await chooseFile(wrapper, new File(["# 标题"], "runbook.md", { type: "text/x-markdown" }));
    await wrapper.get("select").setValue("paragraph");

    await wrapper.get("form").trigger("submit");

    const emittedFile = wrapper.emitted("upload")?.[0]?.[0] as File;
    expect(emittedFile.type).toBe("text/markdown");
  });
});
