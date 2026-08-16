import { describe, expect, it } from "vitest";

import { createApiClient } from "../transport/apiClient";
import { createKnowledgeClient } from "./knowledgeClient";

describe("knowledgeClient", () => {
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
