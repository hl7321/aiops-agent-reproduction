// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { createAppRouter } from "../router";
import { useAuthStore } from "../stores/auth";
import LoginView from "./LoginView.vue";
import RegisterView from "./RegisterView.vue";

async function setup(path: string) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const auth = useAuthStore(pinia);
  auth.status = "anonymous";
  const router = createAppRouter(auth, createMemoryHistory());
  await router.push(path);
  await router.isReady();
  return { pinia, router, auth };
}

describe("认证页面", () => {
  it("认证恢复网络错误以文字告知用户", async () => {
    const { pinia, router, auth } = await setup("/login");
    auth.status = "error";
    auth.errorMessage = "认证服务暂时不可用";

    const wrapper = mount(LoginView, { global: { plugins: [pinia, router] } });

    expect(wrapper.get('[role="alert"]').text()).toContain("认证服务暂时不可用");
  });

  it("登录调用真实 auth store 并返回安全 redirect", async () => {
    const { pinia, router, auth } = await setup("/login?redirect=/knowledge");
    const login = vi.spyOn(auth, "login").mockImplementation(async () => {
      auth.status = "authenticated";
    });
    const wrapper = mount(LoginView, { global: { plugins: [pinia, router] } });

    await wrapper.get('input[type="email"]').setValue("user@example.com");
    await wrapper.get('input[type="password"]').setValue("password-123");
    await wrapper.get("form").trigger("submit");
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe("/knowledge"));

    expect(login).toHaveBeenCalledWith({ email: "user@example.com", password: "password-123" });
  });

  it("注册成功后使用相同凭据登录并进入 chat", async () => {
    const { pinia, router, auth } = await setup("/register");
    const register = vi.spyOn(auth, "register").mockResolvedValue({
      id: "user-1", email: "user@example.com", createdAt: "2026-08-10T00:00:00Z",
    });
    const login = vi.spyOn(auth, "login").mockImplementation(async () => {
      auth.status = "authenticated";
    });
    const wrapper = mount(RegisterView, { global: { plugins: [pinia, router] } });

    await wrapper.get('input[type="email"]').setValue("user@example.com");
    await wrapper.get('input[type="password"]').setValue("password-123");
    await wrapper.get('input[name="confirmPassword"]').setValue("password-123");
    await wrapper.get("form").trigger("submit");
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe("/chat"));

    const payload = { email: "user@example.com", password: "password-123" };
    expect(register).toHaveBeenCalledWith(payload);
    expect(login).toHaveBeenCalledWith(payload);
  });
});
