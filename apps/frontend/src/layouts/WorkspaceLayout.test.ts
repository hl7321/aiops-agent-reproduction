// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import App from "../App.vue";
import { createAppRouter } from "../router";
import { useAiopsStore } from "../stores/aiops";
import { useAuthStore } from "../stores/auth";
import { useChatStore } from "../stores/chat";
import { useChatConfigurationStore } from "../stores/chatConfiguration";
import { useKnowledgeStore } from "../stores/knowledge";
import { useMcpStore } from "../stores/mcp";

async function mountWorkspace(path: string) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const auth = useAuthStore(pinia);
  auth.status = "authenticated";
  auth.user = { id: "user-1", email: "user@example.com", createdAt: "2026-08-10T00:00:00Z" };
  vi.spyOn(auth, "initialize").mockResolvedValue(undefined);
  if (path === "/chat") {
    const chat = useChatStore(pinia);
    const session = {
      id: "session-1", title: "真实会话", memoryMode: "manual" as const,
      memorySummary: null, contextTokens: 0, contextWindowTokens: 1000,
      contextUsagePercent: 0, compactedMessageCount: 0, lastCompactedAt: null,
      canCompact: false, createdAt: "2026-08-20T00:00:00Z", updatedAt: "2026-08-20T00:00:00Z",
    };
    chat.sessions = [session];
    chat.selectedDetail = { session, messages: [] };
    vi.spyOn(chat, "ensureActiveSession").mockResolvedValue(undefined);
    vi.spyOn(useChatConfigurationStore(pinia), "initialize").mockResolvedValue(undefined);
  }
  if (path === "/knowledge") {
    const knowledge = useKnowledgeStore(pinia);
    knowledge.knowledgeBases = [{ id: "kb-1", name: "默认知识库", isDefault: true }];
    knowledge.selectedKnowledgeBaseId = "kb-1";
    vi.spyOn(knowledge, "initialize").mockResolvedValue(undefined);
  }
  if (path === "/mcp") {
    vi.spyOn(useMcpStore(pinia), "initialize").mockResolvedValue(undefined);
  }
  if (path === "/aiops") {
    vi.spyOn(useAiopsStore(pinia), "initialize").mockResolvedValue(undefined);
  }
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
    expect(wrapper.text()).toContain("真实会话");
    expect(wrapper.find(".conversation-panel__empty").exists()).toBe(false);
    expect(wrapper.find(".chat-transcript .app-state").exists()).toBe(false);
    wrapper.unmount();
  });

  it("/knowledge 不显示会话区域且渲染真实工作区", async () => {
    const { wrapper } = await mountWorkspace("/knowledge");

    expect(wrapper.find('[aria-label="会话区域"]').exists()).toBe(false);
    expect(wrapper.get("h1").text()).toBe("知识库");
    expect(wrapper.text()).toContain("文档与索引");
    expect(wrapper.text()).not.toContain("将在后续提案实现");
    expect(wrapper.get('[data-route-canvas="knowledge"]')).toBeTruthy();
    wrapper.unmount();
  });

  it("/aiops 不显示会话区域且渲染真实三栏工作区", async () => {
    const { wrapper } = await mountWorkspace("/aiops");

    expect(wrapper.find('[aria-label="会话区域"]').exists()).toBe(false);
    expect(wrapper.get("h1").text()).toBe("AIOps");
    expect(wrapper.text()).toContain("智能诊断控制台");
    expect(wrapper.text()).not.toContain("将在后续提案实现");
    expect(wrapper.get('[data-route-canvas="aiops"]')).toBeTruthy();
    wrapper.unmount();
  });

  it("/mcp 不显示会话区域且渲染真实连接管理工作区", async () => {
    const { wrapper } = await mountWorkspace("/mcp");

    expect(wrapper.find('[aria-label="会话区域"]').exists()).toBe(false);
    expect(wrapper.get("h1").text()).toBe("MCP");
    expect(wrapper.text()).toContain("MCP Servers");
    expect(wrapper.text()).not.toContain("将在后续提案实现");
    expect(wrapper.get('[data-route-canvas="mcp"]')).toBeTruthy();
    wrapper.unmount();
  });
});
