import { describe, expect, it } from "vitest";

import { createApiClient } from "../transport/apiClient";
import { createChatConfigurationClient } from "./configurationClient";

describe("chat configuration client", () => {
  it("调用七个共享 operation 并保持 Skill FormData", async () => {
    const calls: Array<{ url: string; method: string; body: BodyInit | null | undefined; contentType: string | null }> = [];
    const api = createApiClient({ fetcher: async (input, init) => {
      const headers = new Headers(init?.headers);
      calls.push({ url: String(input), method: init?.method ?? "GET", body: init?.body, contentType: headers.get("Content-Type") });
      const deletion = init?.method === "DELETE";
      return new Response(JSON.stringify({
        ok: true,
        data: deletion ? { deleted: true, assetId: "asset-1" } : {
          prompts: [], skills: [], selectedPromptId: null, selectedSkillIds: [],
        },
        meta: { requestId: "req-1" },
      }), { headers: { "Content-Type": "application/json" } });
    }});
    const client = createChatConfigurationClient(api);
    const form = new FormData();
    form.set("file", new File(["body"], "SKILL.md", { type: "text/markdown" }));

    await client.getConfiguration();
    await client.updateConfiguration({ selectedPromptId: null, selectedSkillIds: [] });
    await client.createPrompt({ label: "值班", content: "简洁" });
    await client.updatePrompt("prompt/1", { label: "值班", content: "明确" });
    await client.deletePrompt("prompt/1");
    await client.uploadSkill(form);
    await client.deleteSkill("skill/1");

    expect(calls.map(({ url, method }) => ({ url, method }))).toEqual([
      { url: "/chat/configuration", method: "GET" },
      { url: "/chat/configuration", method: "PUT" },
      { url: "/chat/prompts", method: "POST" },
      { url: "/chat/prompts/prompt%2F1", method: "PUT" },
      { url: "/chat/prompts/prompt%2F1", method: "DELETE" },
      { url: "/chat/skills", method: "POST" },
      { url: "/chat/skills/skill%2F1", method: "DELETE" },
    ]);
    expect(calls[5]?.body).toBe(form);
    expect(calls[5]?.contentType).toBeNull();
  });
});
