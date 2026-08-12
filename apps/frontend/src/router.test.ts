import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import type { AuthStatus } from "./stores/auth";
import { createAppRouter, resolveSafeRedirect } from "./router";

interface FakeAuth {
  status: AuthStatus;
  initialize: () => Promise<void>;
}

function createAuth(status: AuthStatus): FakeAuth {
  return { status, initialize: vi.fn(async () => undefined) };
}

describe("应用路由守卫", () => {
  it("首次导航只初始化一次并为未登录用户保留 redirect", async () => {
    const auth = createAuth("anonymous");
    const router = createAppRouter(auth, createMemoryHistory());

    await router.push("/knowledge?tab=mine");
    await router.isReady();
    await router.push("/aiops");

    expect(auth.initialize).toHaveBeenCalledOnce();
    expect(router.currentRoute.value.name).toBe("login");
    expect(router.currentRoute.value.query.redirect).toBe("/aiops");
  });

  it("认证恢复完成后继续原受保护目标", async () => {
    const auth = createAuth("idle");
    auth.initialize = vi.fn(async () => { auth.status = "authenticated"; });
    const router = createAppRouter(auth, createMemoryHistory());

    await router.push("/knowledge?tab=mine");
    await router.isReady();

    expect(router.currentRoute.value.fullPath).toBe("/knowledge?tab=mine");
    expect(auth.initialize).toHaveBeenCalledOnce();
  });

  it("已登录访问 publicOnly 页面回到 chat，根路径和未知路由也归一化", async () => {
    const auth = createAuth("authenticated");
    const router = createAppRouter(auth, createMemoryHistory());

    await router.push("/login");
    await router.isReady();
    expect(router.currentRoute.value.fullPath).toBe("/chat");

    await router.push("/");
    expect(router.currentRoute.value.fullPath).toBe("/chat");
    await router.push("/not-a-real-page");
    expect(router.currentRoute.value.fullPath).toBe("/chat");
  });

  it("只接受站内绝对路径 redirect", () => {
    expect(resolveSafeRedirect("/knowledge?tab=mine")).toBe("/knowledge?tab=mine");
    expect(resolveSafeRedirect("https://evil.example/steal")).toBe("/chat");
    expect(resolveSafeRedirect("//evil.example/steal")).toBe("/chat");
    expect(resolveSafeRedirect(["/chat"])).toBe("/chat");
    expect(resolveSafeRedirect(undefined)).toBe("/chat");
  });
});
