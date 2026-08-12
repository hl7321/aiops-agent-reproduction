import { defineStore } from "pinia";
import { ref } from "vue";

import type { AuthUser, LoginRequest, RegisterRequest } from "@super-ai/api-contracts";

import { createAuthClient } from "../auth/authClient";
import type { AuthClient } from "../auth/authClient";
import { publicConfig } from "../config";
import { ApiClientError, createApiClient } from "../transport/apiClient";
import { clearProtectedStores } from "./protectedStoreRegistry";

export const AUTH_TOKEN_STORAGE_KEY = "super-ai.auth.token";

export type AuthStatus = "idle" | "initializing" | "authenticated" | "anonymous" | "error";

export interface AuthStoreDependencies {
  client: AuthClient;
  storage?: Storage;
  clearProtectedState?: () => void;
}

export function createAuthStore(dependencies: AuthStoreDependencies) {
  return defineStore("auth", () => {
    const storage = dependencies.storage ?? globalThis.localStorage;
    const token = ref<string | null>(null);
    const user = ref<AuthUser | null>(null);
    const status = ref<AuthStatus>("idle");
    const errorMessage = ref<string | null>(null);
    let initializePromise: Promise<void> | undefined;

    function clearLocalState(): void {
      storage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      token.value = null;
      user.value = null;
      errorMessage.value = null;
      status.value = "anonymous";
      dependencies.clearProtectedState?.();
    }

    function initialize(): Promise<void> {
      initializePromise ??= restoreAuthentication();
      return initializePromise;
    }

    async function restoreAuthentication(): Promise<void> {
      token.value = storage.getItem(AUTH_TOKEN_STORAGE_KEY);
      if (token.value === null) {
        status.value = "anonymous";
        return;
      }
      status.value = "initializing";
      errorMessage.value = null;
      try {
        const result = await dependencies.client.me();
        user.value = result.data;
        status.value = "authenticated";
      } catch (error: unknown) {
        if (isAuthenticationFailure(error)) {
          clearLocalState();
          status.value = "anonymous";
          return;
        }
        status.value = "error";
        errorMessage.value = error instanceof Error ? error.message : "认证恢复失败";
      }
    }

    async function register(payload: RegisterRequest): Promise<AuthUser> {
      return (await dependencies.client.register(payload)).data;
    }

    async function login(payload: LoginRequest): Promise<void> {
      const result = await dependencies.client.login(payload);
      token.value = result.data.token;
      user.value = result.data.user;
      storage.setItem(AUTH_TOKEN_STORAGE_KEY, result.data.token);
      errorMessage.value = null;
      status.value = "authenticated";
    }

    async function logout(): Promise<void> {
      try {
        if (token.value !== null) {
          await dependencies.client.logout();
        }
      } finally {
        clearLocalState();
      }
    }

    return {
      token, user, status, errorMessage, initialize, register, login, logout, clearLocalState,
    };
  });
}

function isAuthenticationFailure(error: unknown): boolean {
  return error instanceof ApiClientError && error.error.httpStatus === 401;
}

const browserAuthClient = createAuthClient(createApiClient({
  baseUrl: publicConfig.apiBaseUrl,
  getAccessToken: () => globalThis.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? undefined,
  onUnauthorized: () => clearActiveBrowserAuthState(),
}));

const useBrowserAuthStore = createAuthStore({
  client: browserAuthClient,
  clearProtectedState: () => { clearProtectedStores(); },
});

export const useAuthStore = useBrowserAuthStore;

function clearActiveBrowserAuthState(): void {
  useBrowserAuthStore().clearLocalState();
}
