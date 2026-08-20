// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it } from "vitest";

import type { ChatReference } from "@super-ai/api-contracts";

import ChatCitationList from "./ChatCitationList.vue";

function citation(id: string, rerankRank: number, bm25Rank: number | null): ChatReference {
  return {
    chunkId: id, documentId: `doc-${id}`, knowledgeBaseId: "kb-1", source: `${id}.md`,
    excerpt: `excerpt-${id}`, metadata: { heading: "处置" }, vectorRank: rerankRank,
    vectorScore: 0.8, bm25Rank, bm25Score: bm25Rank === null ? null : 1.2,
    rrfScore: 0.02, rerankRank, rerankScore: 1 - rerankRank / 100, score: 1 - rerankRank / 100,
  };
}

describe("ChatCitationList", () => {
  it("按 rerank 排序、最多五条并把未参与分支显示为未命中", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/knowledge", component: { template: "<div />" } }],
    });
    await router.push("/knowledge");
    await router.isReady();
    const wrapper = mount(ChatCitationList, {
      props: { references: [6, 2, 4, 1, 5, 3].map((rank) => citation(`c${rank}`, rank, rank === 1 ? null : rank)) },
      global: { plugins: [router] },
    });
    expect(wrapper.findAll(".citation-card")).toHaveLength(5);
    expect(wrapper.findAll(".citation-card strong")[0]?.text()).toBe("c1.md");
    expect(wrapper.text()).toContain("未命中");
    expect(wrapper.get("a").attributes("href")).toContain("documentId=doc-c1");
  });
});
