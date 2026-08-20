import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatConfigurationData } from "@super-ai/api-contracts";

import type { ChatConfigurationClient } from "../chat/configurationClient";
import type { ApiResult } from "../transport/apiClient";
import { createChatConfigurationStore } from "./chatConfiguration";
import { clearProtectedStores, resetProtectedStoreRegistryForTests } from "./protectedStoreRegistry";

const CONFIG: ChatConfigurationData = {
  prompts: [{ id: "prompt-1", label: "值班", content: "简洁", createdAt: "2026-08-18T00:00:00Z", updatedAt: "2026-08-18T00:00:00Z" }],
  skills: [{ id: "skill-1", name: "knowledge-search", description: "检索", filename: "SKILL.md", content: "BODY", metadata: {}, summary: "检索", createdAt: "2026-08-18T00:00:00Z", updatedAt: "2026-08-18T00:00:00Z" }],
  selectedPromptId: "prompt-1",
  selectedSkillIds: ["skill-1"],
};
const result = <T>(data: T): ApiResult<T> => ({ data, requestId: "req" });

function fakeClient(): ChatConfigurationClient {
  return {
    getConfiguration: vi.fn(async () => result(CONFIG)),
    updateConfiguration: vi.fn(async () => result(CONFIG)),
    createPrompt: vi.fn(async () => result(CONFIG)),
    updatePrompt: vi.fn(async () => result(CONFIG)),
    deletePrompt: vi.fn(async () => result({ deleted: true as const, assetId: "prompt-1" })),
    uploadSkill: vi.fn(async () => result(CONFIG)),
    deleteSkill: vi.fn(async () => result({ deleted: true as const, assetId: "skill-1" })),
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  resetProtectedStoreRegistryForTests();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn(),
      key: vi.fn(() => null), length: 0,
    } satisfies Storage,
  });
});

describe("chat configuration store", () => {
  it("以服务器为事实来源并在 protected cleanup 清空 owner 数据", async () => {
    const client = fakeClient();
    const store = createChatConfigurationStore({ client })();
    await store.initialize();
    expect(store.prompts).toEqual(CONFIG.prompts);
    expect(store.selectedSkillIds).toEqual(["skill-1"]);
    expect(globalThis.localStorage.setItem).not.toHaveBeenCalled();
    clearProtectedStores();
    expect(store.prompts).toEqual([]);
    expect(store.skills).toEqual([]);
    expect(store.selectedPromptId).toBeNull();
  });

  it("所有成功写操作使用服务端 DTO 对账，删除后重新读取", async () => {
    const client = fakeClient();
    const store = createChatConfigurationStore({ client })();
    await store.updateSelection(null, []);
    await store.createPrompt({ label: "x", content: "y" });
    await store.updatePrompt("prompt-1", { label: "x", content: "z" });
    const form = new FormData();
    await store.uploadSkill(form);
    await store.deletePrompt("prompt-1");
    await store.deleteSkill("skill-1");
    expect(client.getConfiguration).toHaveBeenCalledTimes(2);
    expect(store.prompts).toEqual(CONFIG.prompts);
  });
});
