import { defineStore } from "pinia";
import { ref } from "vue";

import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

export const useProtectedDataStore = defineStore("protected-data", () => {
  const chatDraft = ref("");
  const selectedKnowledgeBaseIds = ref<string[]>([]);
  const aiopsView = ref<string | null>(null);

  function clear(): void {
    chatDraft.value = "";
    selectedKnowledgeBaseIds.value = [];
    aiopsView.value = null;
  }

  registerProtectedStoreCleanup(clear);
  return { chatDraft, selectedKnowledgeBaseIds, aiopsView, clear };
});
