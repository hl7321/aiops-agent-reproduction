// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { ChunkPreviewData, DocumentIndexTask, KnowledgeDocument } from "@super-ai/api-contracts";

import KnowledgeDocumentTable from "./KnowledgeDocumentTable.vue";

const document: KnowledgeDocument = {
  id: "doc-1", knowledgeBaseId: "kb-1", filename: "very-long-runbook-name.md",
  sizeBytes: 1_024, mimeType: "text/markdown", sha256: "abc", uploadedAt: "2026-08-17T00:00:00Z",
  indexStatus: "failed", chunkingConfig: { strategy: "paragraph" },
};
const task: DocumentIndexTask = {
  id: "task-1", knowledgeBaseId: "kb-1", documentId: "doc-1", status: "failed",
  failureReason: "向量服务暂不可用", createdAt: "2026-08-17T00:00:00Z",
  updatedAt: "2026-08-17T00:00:01Z",
};
const preview: ChunkPreviewData = {
  totalChunks: 1,
  items: [{ index: 0, excerpt: "真实切分正文", metadata: { heading: "故障处理", source: "runbook.md" } }],
};

describe("KnowledgeDocumentTable", () => {
  it("详情默认折叠，展开后显示真实 preview、metadata 和失败重试", async () => {
    const wrapper = mount(KnowledgeDocumentTable, { props: {
      documents: [document], tasksByDocument: { [document.id]: task },
      selectedDocument: null, previewsByDocument: {},
    }});
    expect(wrapper.find(".knowledge-document-detail").exists()).toBe(false);

    await wrapper.get('button[aria-label="展开 very-long-runbook-name.md 详情"]').trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual([document.id]);
    await wrapper.setProps({ selectedDocument: document, previewsByDocument: { [document.id]: preview } });

    expect(wrapper.get(".knowledge-document-detail").text()).toContain("真实切分正文");
    expect(wrapper.get(".knowledge-document-detail").text()).toContain("向量服务暂不可用");
    expect(wrapper.get(".metadata-scroll").attributes("tabindex")).toBe("0");
    expect(wrapper.get(".preview-scroll").attributes("tabindex")).toBe("0");
    expect(wrapper.get(".knowledge-table-scroll").attributes("tabindex")).toBe("0");
    expect(wrapper.find('button[aria-label="重试 very-long-runbook-name.md 索引"]').exists()).toBe(true);
  });

  it("所有索引状态都有文字且删除与重建是显式动作", async () => {
    const wrapper = mount(KnowledgeDocumentTable, { props: {
      documents: [{ ...document, indexStatus: "succeeded" }], tasksByDocument: {},
      selectedDocument: null, previewsByDocument: {},
    }});
    expect(wrapper.get('[role="status"]').text()).toContain("索引成功");

    await wrapper.get('button[aria-label="重新索引 very-long-runbook-name.md"]').trigger("click");
    await wrapper.get('button[aria-label="删除 very-long-runbook-name.md"]').trigger("click");
    expect(wrapper.emitted("rebuild")?.[0]).toEqual([document.id]);
    expect(wrapper.emitted("delete")?.[0]).toEqual([document.id]);
  });
});
