import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthUser, LoginData, LoginRequest, LogoutData, RegisterRequest } from "@super-ai/api-contracts";

import { ApiClientError } from "../transport/apiClient";
import type { ApiResult } from "../transport/apiClient";
import type { AuthClient } from "../auth/authClient";
import { AUTH_TOKEN_STORAGE_KEY, createAuthStore } from "./auth";

const USER: AuthUser = {
  id: "user-1",
  email: "user@example.com",
  createdAt: "2026-08-08T00:00:00Z",
};

class MemoryStorage implements Storage {
  readonly values = new Map<string, string>();
  readonly writes: string[] = [];

  get length(): number { return this.values.size; }
  clear(): void { this.values.clear(); }
  getItem(key: string): string | null { return this.values.get(key) ?? null; }
  key(index: number): string | null { return [...this.values.keys()][index] ?? null; }
  removeItem(key: string): void { this.values.delete(key); }
  setItem(key: string, value: string): void { this.values.set(key, value); this.writes.push(key); }
}

function result<T>(data: T): ApiResult<T> {
  return { data, requestId: "req-auth" };
}

function fakeClient(overrides: Partial<AuthClient> = {}): AuthClient {
  return {
    register: async (_payload: RegisterRequest) => result(USER),
    login: async (_payload: LoginRequest) => result<LoginData>({ user: USER, token: "raw-token" }),
    logout: async () => result<LogoutData>({ revoked: true }),
    me: async () => result(USER),
    ...overrides,
  };
}

beforeEach(() => setActivePinia(createPinia()));

describe("auth state", () => {
  it("共享 401 清理入口同时切换为匿名状态", async () => {
    const storage = new MemoryStorage();
    const useStore = createAuthStore({ client: fakeClient(), storage });
    const store = useStore();
    await store.login({ email: "user@example.com", password: "password-123" });

    store.clearLocalState();

    expect(store.status).toBe("anonymous");
    expect(store.token).toBeNull();
    expect(store.user).toBeNull();
  });

  it("login 只把 token 写入 localStorage", async () => {
    const storage = new MemoryStorage();
    const useStore = createAuthStore({ client: fakeClient(), storage });
    const store = useStore();

    await store.login({ email: "user@example.com", password: "password-123" });

    expect(store.user).toEqual(USER);
    expect(store.status).toBe("authenticated");
    expect(storage.values).toEqual(new Map([[AUTH_TOKEN_STORAGE_KEY, "raw-token"]]));
    expect(storage.writes).toEqual([AUTH_TOKEN_STORAGE_KEY]);
  });

  it("initialize 使用现有 token 调用 me 并恢复用户", async () => {
    const storage = new MemoryStorage();
    storage.setItem(AUTH_TOKEN_STORAGE_KEY, "stored-token");
    const me = vi.fn(async () => result(USER));
    const useStore = createAuthStore({ client: fakeClient({ me }), storage });
    const store = useStore();

    await Promise.all([store.initialize(), store.initialize()]);

    expect(me).toHaveBeenCalledOnce();
    expect(store.token).toBe("stored-token");
    expect(store.user).toEqual(USER);
    expect([...storage.values.keys()]).toEqual([AUTH_TOKEN_STORAGE_KEY]);
  });

  it("失效 token 清除本地受保护状态但不调用业务删除", async () => {
    const storage = new MemoryStorage();
    storage.setItem(AUTH_TOKEN_STORAGE_KEY, "expired-token");
    const clearProtectedState = vi.fn();
    const me = vi.fn(async () => {
      throw new ApiClientError({
        code: "AUTH_REQUIRED",
        category: "authentication",
        httpStatus: 401,
        message: "需要认证后才能访问",
      }, "req-invalid");
    });
    const useStore = createAuthStore({ client: fakeClient({ me }), storage, clearProtectedState });
    const store = useStore();

    await store.initialize();

    expect(store.status).toBe("anonymous");
    expect(store.token).toBeNull();
    expect(store.user).toBeNull();
    expect(storage.length).toBe(0);
    expect(clearProtectedState).toHaveBeenCalledOnce();
  });

  it("网络故障保留 token，logout 无论结果都清理本地状态", async () => {
    const storage = new MemoryStorage();
    storage.setItem(AUTH_TOKEN_STORAGE_KEY, "stored-token");
    const clearProtectedState = vi.fn();
    const me = vi.fn(async () => { throw new TypeError("network unavailable"); });
    const logout = vi.fn(async () => { throw new TypeError("network unavailable"); });
    const useStore = createAuthStore({
      client: fakeClient({ me, logout }), storage, clearProtectedState,
    });
    const store = useStore();

    await store.initialize();
    expect(store.status).toBe("error");
    expect(store.token).toBe("stored-token");

    await expect(store.logout()).rejects.toThrow("network unavailable");
    expect(store.status).toBe("anonymous");
    expect(storage.length).toBe(0);
    expect(clearProtectedState).toHaveBeenCalledOnce();
  });
});
