import { defineStore } from "pinia";
import { ref } from "vue";

import type {
  FeedbackTargetType,
  UserFeedback,
  UserFeedbackUpsertRequest,
} from "@super-ai/api-contracts";

import { createUserFeedbackClient } from "../feedback/feedbackClient";
import type { UserFeedbackClient } from "../feedback/feedbackClient";
import { publicConfig } from "../config";
import { createApiClient } from "../transport/apiClient";
import { AUTH_TOKEN_STORAGE_KEY, useAuthStore } from "./auth";
import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

export interface UserFeedbackStoreDependencies { readonly client: UserFeedbackClient; }

function groupKey(targetType: FeedbackTargetType, targetId: string): string {
  return `${targetType}:${targetId}`;
}

function itemKey(
  targetType: FeedbackTargetType, targetId: string, subjectId: string | null,
): string {
  return `${groupKey(targetType, targetId)}:${subjectId ?? ""}`;
}

export function createUserFeedbackStore(dependencies: UserFeedbackStoreDependencies) {
  return defineStore("userFeedback", () => {
    const itemsByKey = ref<Record<string, UserFeedback>>({});
    const errorsByKey = ref<Record<string, string>>({});
    const loadedGroups = new Set<string>();
    const pendingLoads = new Map<string, Promise<void>>();
    let generation = 0;

    function find(
      targetType: FeedbackTargetType, targetId: string, subjectId: string | null,
    ): UserFeedback | undefined {
      return itemsByKey.value[itemKey(targetType, targetId, subjectId)];
    }

    function errorFor(
      targetType: FeedbackTargetType, targetId: string, subjectId: string | null,
    ): string | undefined {
      return errorsByKey.value[itemKey(targetType, targetId, subjectId)];
    }

    async function load(targetType: FeedbackTargetType, targetId: string): Promise<void> {
      const group = groupKey(targetType, targetId);
      if (loadedGroups.has(group)) return;
      const pending = pendingLoads.get(group);
      if (pending !== undefined) return pending;
      const expectedGeneration = generation;
      const request = dependencies.client.list(targetType, targetId).then((response) => {
        if (generation !== expectedGeneration) return;
        const retained = Object.fromEntries(
          Object.entries(itemsByKey.value).filter(([key]) => !key.startsWith(`${group}:`)),
        );
        for (const item of response.data.items) {
          retained[itemKey(item.targetType, item.targetId, item.subjectId)] = item;
        }
        itemsByKey.value = retained;
        loadedGroups.add(group);
      }).finally(() => pendingLoads.delete(group));
      pendingLoads.set(group, request);
      return request;
    }

    async function save(body: UserFeedbackUpsertRequest): Promise<UserFeedback> {
      const key = itemKey(body.targetType, body.targetId, body.subjectId ?? null);
      delete errorsByKey.value[key];
      try {
        const response = await dependencies.client.upsert(body);
        itemsByKey.value = { ...itemsByKey.value, [key]: response.data };
        return response.data;
      } catch (error: unknown) {
        errorsByKey.value[key] = error instanceof Error ? error.message : "反馈保存失败";
        throw error;
      }
    }

    async function remove(item: UserFeedback): Promise<void> {
      const key = itemKey(item.targetType, item.targetId, item.subjectId);
      delete errorsByKey.value[key];
      try {
        await dependencies.client.delete(item.id);
        const next = { ...itemsByKey.value };
        delete next[key];
        itemsByKey.value = next;
      } catch (error: unknown) {
        errorsByKey.value[key] = error instanceof Error ? error.message : "反馈删除失败";
        throw error;
      }
    }

    function reset(): void {
      generation += 1;
      itemsByKey.value = {};
      errorsByKey.value = {};
      loadedGroups.clear();
      pendingLoads.clear();
    }

    registerProtectedStoreCleanup(reset);
    return { itemsByKey, errorsByKey, find, errorFor, load, save, remove, reset };
  });
}

const browserClient = createUserFeedbackClient(createApiClient({
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => useAuthStore().clearLocalState(),
}));

export const useUserFeedbackStore = createUserFeedbackStore({ client: browserClient });
