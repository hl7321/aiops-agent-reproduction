// @vitest-environment happy-dom
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KnowledgeBase, KnowledgeDocument } from "@super-ai/api-contracts";

import { useKnowledgeStore } from "../stores/knowledge";
import KnowledgeView from "./KnowledgeView.vue";

const kb: KnowledgeBase = { id: "kb-1", name: "默认知识库", isDefault: true };
const document: KnowledgeDocument = {
  id: "doc-1", knowledgeBaseId: kb.id, filename: "runbook.md", sizeBytes: 10,
  mimeType: "text/markdown", sha256: "hash", uploadedAt: "2026-08-17T00:00:00Z",
  indexStatus: "pending", chunkingConfig: { strategy: "paragraph" },
};

beforeEach(() => setActivePinia(createPinia()));

describe("KnowledgeView", () => {
  it("初始化真实 store，单知识库不显示 selector 并呈现中文工作区", async () => {
    const store = useKnowledgeStore();
    store.knowledgeBases = [kb];
    store.selectedKnowledgeBaseId = kb.id;
    store.documents = [document];
    store.initialize = vi.fn(async () => undefined);
    const wrapper = mount(KnowledgeView);
    await flushPromises();

    expect(store.initialize).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("文档与索引");
    expect(wrapper.find('select[aria-label="选择知识库"]').exists()).toBe(false);
    expect(wrapper.get(".knowledge-document-list").attributes("aria-label")).toBe("知识文档列表");
  });

  it("覆盖和删除都显示明确中文确认", async () => {
    const store = useKnowledgeStore();
    store.knowledgeBases = [kb];
    store.selectedKnowledgeBaseId = kb.id;
    store.documents = [document];
    store.overwriteConfirmation = { filename: document.filename };
    store.deleteConfirmation = document;
    store.initialize = vi.fn(async () => undefined);
    const wrapper = mount(KnowledgeView);
    await flushPromises();

    expect(wrapper.get('[role="dialog"][aria-label="确认覆盖文档"]').text()).toContain("覆盖");
    expect(wrapper.get('[role="dialog"][aria-label="确认删除文档"]').text()).toContain("删除");
  });
});
