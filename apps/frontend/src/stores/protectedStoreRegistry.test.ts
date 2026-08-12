import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useProtectedDataStore } from "./protectedData";
import {
  clearProtectedStores,
  registerProtectedStoreCleanup,
  resetProtectedStoreRegistryForTests,
} from "./protectedStoreRegistry";

beforeEach(() => {
  setActivePinia(createPinia());
  resetProtectedStoreRegistryForTests();
});

describe("受保护 store 清理注册机制", () => {
  it("执行所有仍注册的清理器并隔离单个失败", () => {
    const first = vi.fn();
    const failed = vi.fn(() => { throw new Error("cleanup failed"); });
    const removed = vi.fn();
    registerProtectedStoreCleanup(first);
    registerProtectedStoreCleanup(failed);
    const unregister = registerProtectedStoreCleanup(removed);
    unregister();

    const errors = clearProtectedStores();

    expect(first).toHaveBeenCalledOnce();
    expect(failed).toHaveBeenCalledOnce();
    expect(removed).not.toHaveBeenCalled();
    expect(errors).toHaveLength(1);
  });

  it("protectedData 只保存在内存并可统一清空", () => {
    const store = useProtectedDataStore();
    store.chatDraft = "尚未发送";
    store.selectedKnowledgeBaseIds = ["kb-1"];
    store.aiopsView = "alerts";

    clearProtectedStores();

    expect(store.chatDraft).toBe("");
    expect(store.selectedKnowledgeBaseIds).toEqual([]);
    expect(store.aiopsView).toBeNull();
  });
});
