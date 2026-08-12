// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import App from "../App.vue";
import { createAppRouter } from "../router";
import { useAuthStore } from "../stores/auth";

async function mountWorkspace(path: string) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const auth = useAuthStore(pinia);
  auth.status = "authenticated";
  auth.user = { id: "user-1", email: "user@example.com", createdAt: "2026-08-10T00:00:00Z" };
  vi.spyOn(auth, "initialize").mockResolvedValue(undefined);
  const router = createAppRouter(auth, createMemoryHistory());
  await router.push(path);
  await router.isReady();
  const wrapper = mount(App, { attachTo: document.body, global: { plugins: [pinia, router] } });
  await wrapper.vm.$nextTick();
  return { wrapper, router };
}

describe("WorkspaceLayout", () => {
  it("Chat 同时显示 rail、会话区域、顶栏和路由画布", async () => {
    const { wrapper } = await mountWorkspace("/chat");

    expect(wrapper.get('[aria-label="主导航"]')).toBeTruthy();
    expect(wrapper.get('[aria-label="会话区域"]')).toBeTruthy();
    expect(wrapper.get("h1").text()).toBe("Chat");
    expect(wrapper.text()).toContain("user@example.com");
    expect(wrapper.text()).toContain("服务状态");
    expect(wrapper.get('[data-route-canvas="chat"]')).toBeTruthy();
    wrapper.unmount();
  });

  it.each([
    ["/knowledge", "知识库"],
    ["/aiops", "AIOps"],
    ["/mcp", "MCP"],
  ])("%s 不显示会话区域且明确为后续能力", async (path, title) => {
    const { wrapper } = await mountWorkspace(path);

    expect(wrapper.find('[aria-label="会话区域"]').exists()).toBe(false);
    expect(wrapper.get("h1").text()).toBe(title);
    expect(wrapper.text()).toContain("将在后续提案实现");
    expect(wrapper.get("[data-route-canvas]")).toBeTruthy();
    wrapper.unmount();
  });
});
