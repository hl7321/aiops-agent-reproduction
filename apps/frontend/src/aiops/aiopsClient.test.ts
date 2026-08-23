import { describe, expect, it } from "vitest";

import { createApiClient } from "../transport/apiClient";
import { createSseClient } from "../transport/sseClient";
import { createAiopsClient } from "./aiopsClient";

describe("aiopsClient", () => {
  it("只调用共享合同登记的真实 REST 路径", async () => {
    const calls: Array<{ url: string; method: string; body?: string }> = [];
    const api = createApiClient({ fetcher: async (input, init) => {
      calls.push({
        url: String(input), method: init?.method ?? "GET",
        ...(typeof init?.body === "string" ? { body: init.body } : {}),
      });
      return new Response(JSON.stringify({
        ok: true, data: {}, meta: { requestId: "req-aiops" },
      }), { headers: { "Content-Type": "application/json" } });
    }});
    const client = createAiopsClient(api, createSseClient());

    await client.listActiveAlerts();
    await client.createDiagnostic({ query: "手工排查", alerts: [] });
    await client.listDiagnostics();
    await client.getDiagnostic("task/1");
    await client.getEvidenceChain("task/1");
    await client.cancelBackgroundJob("job/1");
    await client.listCases();
    await client.getCase("case/1");
    await client.promoteDiagnostic("task/1", { resolution: "merge", candidateCaseId: "case/1" });
    await client.listKnowledgeBases();

    expect(calls).toEqual([
      { url: "/aiops/alerts/active", method: "GET" },
      { url: "/aiops/diagnostics", method: "POST", body: '{"query":"手工排查","alerts":[]}' },
      { url: "/aiops/diagnostics", method: "GET" },
      { url: "/aiops/diagnostics/task%2F1", method: "GET" },
      { url: "/aiops/diagnostics/task%2F1/evidence-chain", method: "GET" },
      { url: "/background-jobs/job%2F1:cancel", method: "POST" },
      { url: "/aiops/diagnostic-cases", method: "GET" },
      { url: "/aiops/diagnostic-cases/case%2F1", method: "GET" },
      { url: "/aiops/diagnostics/task%2F1:promote-to-knowledge", method: "POST",
        body: '{"resolution":"merge","candidateCaseId":"case/1"}' },
      { url: "/knowledge-bases", method: "GET" },
    ]);
  });

  it("通过共享 SSE 客户端发送持久 sequence，且不添加 context", async () => {
    let request = { url: "", method: "", body: "" };
    const encoded = new TextEncoder().encode(
      'data: {"id":"job:8","sequence":8,"type":"task.status","channel":"aiops","timestamp":"now","data":{"taskId":"task-1","status":"running","message":"执行中"}}\n\n',
    );
    const sse = createSseClient({ fetcher: async (input, init) => {
      request = { url: String(input), method: init?.method ?? "GET", body: String(init?.body ?? "") };
      return new Response(new ReadableStream<Uint8Array>({
        start(controller) { controller.enqueue(encoded); controller.close(); },
      }));
    }});
    const client = createAiopsClient(createApiClient(), sse);
    const events = [];
    for await (const event of client.streamDiagnostic("task/1", 7)) events.push(event);

    expect(request).toEqual({
      url: "/aiops/diagnostics/task%2F1:stream", method: "POST", body: '{"afterSequence":7}',
    });
    expect(events[0]?.sequence).toBe(8);
    expect(request.body).not.toContain("context");
  });
});
