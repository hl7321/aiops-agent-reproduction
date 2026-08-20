import { defineStore } from "pinia";
import { ref } from "vue";

import type {
  CreateMcpConnectionRequest,
  McpConnection,
  McpConnectionCheckResult,
} from "@super-ai/api-contracts";

import { createMcpClient } from "../mcp/mcpClient";
import type { McpClient } from "../mcp/mcpClient";
import { publicConfig } from "../config";
import { createApiClient } from "../transport/apiClient";
import { AUTH_TOKEN_STORAGE_KEY, useAuthStore } from "./auth";
import { registerProtectedStoreCleanup } from "./protectedStoreRegistry";

export interface McpStoreDependencies {
  readonly client: McpClient;
}

export function createMcpStore(dependencies: McpStoreDependencies) {
  return defineStore("mcp", () => {
    const connections = ref<readonly McpConnection[]>([]);
    const editingId = ref<string | null>(null);
    const checkById = ref<Record<string, McpConnectionCheckResult>>({});
    const deleteConfirmation = ref<McpConnection | null>(null);
    const loading = ref(false);
    const saving = ref(false);
    const errorMessage = ref<string | null>(null);
    let generation = 0;

    async function initialize(): Promise<void> {
      const requestGeneration = generation;
      loading.value = true;
      errorMessage.value = null;
      try {
        const loaded = (await dependencies.client.listConnections()).data.connections;
        if (requestGeneration === generation) connections.value = loaded;
      } catch (error: unknown) {
        if (requestGeneration === generation) {
          errorMessage.value = message(error, "MCP 连接加载失败");
        }
        throw error;
      } finally {
        if (requestGeneration === generation) loading.value = false;
      }
    }

    async function create(body: CreateMcpConnectionRequest): Promise<void> {
      const requestGeneration = generation;
      saving.value = true;
      try {
        const created = (await dependencies.client.createConnection(body)).data;
        if (requestGeneration === generation) {
          replace(created);
          editingId.value = null;
        }
      } finally {
        if (requestGeneration === generation) saving.value = false;
      }
    }

    async function update(id: string, body: CreateMcpConnectionRequest): Promise<void> {
      const requestGeneration = generation;
      saving.value = true;
      try {
        const updated = (await dependencies.client.updateConnection(id, body)).data;
        if (requestGeneration === generation) {
          replace(updated);
          const nextChecks = { ...checkById.value };
          delete nextChecks[id];
          checkById.value = nextChecks;
          editingId.value = null;
        }
      } finally {
        if (requestGeneration === generation) saving.value = false;
      }
    }

    async function toggleEnabled(id: string, enabled: boolean): Promise<void> {
      const current = connections.value.find((item) => item.id === id);
      if (current === undefined) throw new Error("MCP 连接不存在");
      await update(id, {
        name: current.name, transport: current.transport, url: current.url, enabled,
        timeoutSeconds: current.timeoutSeconds, retries: current.retries,
      });
    }

    async function check(id: string): Promise<void> {
      const requestGeneration = generation;
      const result = (await dependencies.client.checkConnection(id)).data;
      if (requestGeneration === generation) {
        checkById.value = { ...checkById.value, [id]: result };
        replace(result.connection);
      }
    }

    function requestDelete(id: string): void {
      deleteConfirmation.value = connections.value.find((item) => item.id === id) ?? null;
    }

    async function confirmDelete(): Promise<void> {
      const target = deleteConfirmation.value;
      if (target === null) return;
      const requestGeneration = generation;
      await dependencies.client.deleteConnection(target.id);
      if (requestGeneration !== generation) return;
      connections.value = connections.value.filter((item) => item.id !== target.id);
      const nextChecks = { ...checkById.value };
      delete nextChecks[target.id];
      checkById.value = nextChecks;
      deleteConfirmation.value = null;
      if (editingId.value === target.id) editingId.value = null;
    }

    function cancelDelete(): void {
      deleteConfirmation.value = null;
    }

    function replace(connection: McpConnection): void {
      const index = connections.value.findIndex((item) => item.id === connection.id);
      connections.value = index < 0
        ? [connection, ...connections.value]
        : connections.value.map((item) => item.id === connection.id ? connection : item);
    }

    function reset(): void {
      generation += 1;
      connections.value = [];
      editingId.value = null;
      checkById.value = {};
      deleteConfirmation.value = null;
      loading.value = false;
      saving.value = false;
      errorMessage.value = null;
    }

    registerProtectedStoreCleanup(reset);
    return {
      connections, editingId, checkById, deleteConfirmation, loading, saving, errorMessage,
      initialize, create, update, toggleEnabled, check, requestDelete, confirmDelete,
      cancelDelete, reset,
    };
  });
}

function message(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

const browserClient = createMcpClient(createApiClient({
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => useAuthStore().clearLocalState(),
}));

export const useMcpStore = createMcpStore({ client: browserClient });
