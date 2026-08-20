import { describe, expect, it } from "vitest";

import { createApiClient } from "../transport/apiClient";
import { createKnowledgeClient } from "./knowledgeClient";

describe("knowledgeClient", () => {
  it("使用共享路径读取知识库、文档、详情、预览与 background jobs", async () => {
    const calls: Array<{ url: string; method: string }> = [];
    const responses: readonly unknown[] = [
      { items: [{ id: "kb-1", name: "默认知识库", isDefault: true }] },
      { items: [] },
      {
        id: "doc-1", knowledgeBaseId: "kb-1", filename: "a.md", sizeBytes: 1,
        mimeType: "text/markdown", sha256: "hash", uploadedAt: "2026-08-16T00:00:00Z",
        indexStatus: "succeeded", chunkingConfig: { strategy: "paragraph" },
      },
      { totalChunks: 1, items: [{ index: 0, excerpt: "正文", metadata: { page: 1 } }] },
      { items: [] },
    ];
    const api = createApiClient({ fetcher: async (input, init) => {
      calls.push({ url: String(input), method: init?.method ?? "GET" });
      return new Response(JSON.stringify({
        ok: true, data: responses[calls.length - 1], meta: { requestId: `req-${calls.length}` },
      }), { headers: { "Content-Type": "application/json" } });
    }});
    const client = createKnowledgeClient(api);

    await client.listKnowledgeBases();
    await client.listDocuments("kb/1");
    await client.getDocument("kb/1", "doc 1");
    await client.getChunkPreview("kb/1", "doc 1");
    await client.listBackgroundJobs();

    expect(calls).toEqual([
      { url: "/knowledge-bases", method: "GET" },
      { url: "/knowledge-bases/kb%2F1/documents", method: "GET" },
      { url: "/knowledge-bases/kb%2F1/documents/doc%201", method: "GET" },
      { url: "/knowledge-bases/kb%2F1/documents/doc%201/chunk-preview", method: "GET" },
      { url: "/background-jobs", method: "GET" },
    ]);
  });

  it("删除文档使用 DELETE 并返回服务端文档 DTO", async () => {
    let request: { url: string; method: string } | undefined;
    const api = createApiClient({ fetcher: async (input, init) => {
      request = { url: String(input), method: init?.method ?? "GET" };
      return new Response(JSON.stringify({
        ok: true,
        data: {
          id: "doc-1", knowledgeBaseId: "kb-1", filename: "a.md", sizeBytes: 1,
          mimeType: "text/markdown", sha256: "hash", uploadedAt: "2026-08-16T00:00:00Z",
          indexStatus: "succeeded", chunkingConfig: { strategy: "paragraph" },
        },
        meta: { requestId: "req-delete" },
      }), { headers: { "Content-Type": "application/json" } });
    }});

    const result = await createKnowledgeClient(api).deleteDocument("kb-1", "doc-1");

    expect(request).toEqual({
      url: "/knowledge-bases/kb-1/documents/doc-1",
      method: "DELETE",
    });
    expect(result.data.id).toBe("doc-1");
  });

  it("multipart 上传保持 FormData 和策略 JSON 原样交给 ApiClient", async () => {
    let body: BodyInit | null | undefined;
    const api = createApiClient({ fetcher: async (_input, init) => {
      body = init?.body;
      return new Response(JSON.stringify({
        ok: true,
        data: {
          id: "doc-1", knowledgeBaseId: "kb-1", filename: "a.md", sizeBytes: 1,
          mimeType: "text/markdown", sha256: "hash", uploadedAt: "2026-08-16T00:00:00Z",
          indexStatus: "pending", chunkingConfig: {
            strategy: "fixed-character", maxCharacters: 1200, overlap: 200,
          },
        },
        meta: { requestId: "req-upload" },
      }), { status: 201, headers: { "Content-Type": "application/json" } });
    }});
    const form = new FormData();
    form.set("file", new File(["正文"], "a.md", { type: "text/markdown" }));
    form.set("chunkingConfig", JSON.stringify({
      strategy: "fixed-character", maxCharacters: 1200, overlap: 200,
    }));
    form.set("overwrite", "false");

    await createKnowledgeClient(api).uploadDocument("kb-1", form);

    expect(body).toBe(form);
    expect((body as FormData).get("chunkingConfig")).toBe(
      '{"strategy":"fixed-character","maxCharacters":1200,"overlap":200}',
    );
  });

  it("上传成功后显式创建首次 durable index task", async () => {
    const calls: Array<{ url: string; method: string }> = [];
    const api = createApiClient({ fetcher: async (input, init) => {
      calls.push({ url: String(input), method: init?.method ?? "GET" });
      const isUpload = calls.length === 1;
      return new Response(JSON.stringify({
        ok: true,
        data: isUpload ? {
          id: "doc-1", knowledgeBaseId: "kb-1", filename: "a.md", sizeBytes: 1,
          mimeType: "text/markdown", sha256: "a", uploadedAt: "2026-08-13T00:00:00Z",
          indexStatus: "pending", chunkingConfig: { strategy: "paragraph" },
        } : {
          id: "task-1", knowledgeBaseId: "kb-1", documentId: "doc-1", status: "pending",
          createdAt: "2026-08-13T00:00:00Z", updatedAt: "2026-08-13T00:00:00Z",
        },
        meta: { requestId: `req-${calls.length}` },
      }), { status: isUpload ? 201 : 201, headers: { "Content-Type": "application/json" } });
    }});
    const client = createKnowledgeClient(api);
    const form = new FormData();
    form.set("file", new File(["x"], "a.md", { type: "text/markdown" }));

    const result = await client.uploadAndCreateIndexTask("kb-1", form);

    expect(calls).toEqual([
      { url: "/knowledge-bases/kb-1/documents", method: "POST" },
      { url: "/knowledge-bases/kb-1/documents/doc-1/index-tasks", method: "POST" },
    ]);
    expect(result.task.status).toBe("pending");
  });

  it("上传失败时不创建索引任务", async () => {
    let calls = 0;
    const api = createApiClient({ fetcher: async () => {
      calls += 1;
      return new Response(JSON.stringify({
        ok: false,
        error: { code: "VALIDATION_REQUEST_INVALID", category: "validation", httpStatus: 422, message: "bad" },
        meta: { requestId: "req-bad" },
      }), { status: 422, headers: { "Content-Type": "application/json" } });
    }});
    const form = new FormData();
    form.set("file", new File(["x"], "bad.txt", { type: "text/plain" }));

    await expect(createKnowledgeClient(api).uploadAndCreateIndexTask("kb-1", form)).rejects.toThrow("bad");
    expect(calls).toBe(1);
  });
});
