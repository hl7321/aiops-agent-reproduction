import { defineStore } from "pinia";
import { ref } from "vue";

import type {
  ChatConfigurationData,
  ChatPrompt,
  ChatSkill,
  CreateChatPromptRequest,
  UpdateChatPromptRequest,
} from "@super-ai/api-contracts";

import { createChatConfigurationClient } from "../chat/configurationClient";
import type { ChatConfigurationClient } from "../chat/configurationClient";
import { publicConfig } from "../config";
import { createApiClient } from "../transport/apiClient";
import { AUTH_TOKEN_STORAGE_KEY, useAuthStore } from "./auth";
import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

export interface ChatConfigurationStoreDependencies {
  readonly client: ChatConfigurationClient;
}

export function createChatConfigurationStore(dependencies: ChatConfigurationStoreDependencies) {
  return defineStore("chatConfiguration", () => {
    const prompts = ref<readonly ChatPrompt[]>([]);
    const skills = ref<readonly ChatSkill[]>([]);
    const selectedPromptId = ref<string | null>(null);
    const selectedSkillIds = ref<readonly string[]>([]);
    const loading = ref(false);
    const errorMessage = ref<string | null>(null);

    function apply(data: ChatConfigurationData): void {
      prompts.value = data.prompts;
      skills.value = data.skills;
      selectedPromptId.value = data.selectedPromptId;
      selectedSkillIds.value = data.selectedSkillIds;
    }

    async function initialize(): Promise<void> {
      loading.value = true;
      errorMessage.value = null;
      try {
        apply((await dependencies.client.getConfiguration()).data);
      } catch (error: unknown) {
        errorMessage.value = error instanceof Error ? error.message : "Chat 配置加载失败";
        throw error;
      } finally {
        loading.value = false;
      }
    }

    async function updateSelection(promptId: string | null, skillIds: readonly string[]): Promise<void> {
      apply((await dependencies.client.updateConfiguration({
        selectedPromptId: promptId, selectedSkillIds: skillIds,
      })).data);
    }

    async function createPrompt(body: CreateChatPromptRequest): Promise<void> {
      apply((await dependencies.client.createPrompt(body)).data);
    }

    async function updatePrompt(id: string, body: UpdateChatPromptRequest): Promise<void> {
      apply((await dependencies.client.updatePrompt(id, body)).data);
    }

    async function deletePrompt(id: string): Promise<void> {
      await dependencies.client.deletePrompt(id);
      await initialize();
    }

    async function uploadSkill(form: FormData): Promise<void> {
      apply((await dependencies.client.uploadSkill(form)).data);
    }

    async function deleteSkill(id: string): Promise<void> {
      await dependencies.client.deleteSkill(id);
      await initialize();
    }

    function reset(): void {
      prompts.value = [];
      skills.value = [];
      selectedPromptId.value = null;
      selectedSkillIds.value = [];
      loading.value = false;
      errorMessage.value = null;
    }

    registerProtectedStoreCleanup(reset);
    return {
      prompts, skills, selectedPromptId, selectedSkillIds, loading, errorMessage,
      initialize, updateSelection, createPrompt, updatePrompt, deletePrompt,
      uploadSkill, deleteSkill, reset,
    };
  });
}

const browserClient = createChatConfigurationClient(createApiClient({
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => useAuthStore().clearLocalState(),
}));

export const useChatConfigurationStore = createChatConfigurationStore({ client: browserClient });
