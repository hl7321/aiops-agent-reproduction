// @vitest-environment happy-dom
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { McpConnection } from "@super-ai/api-contracts";

import { useMcpStore } from "../stores/mcp";
import McpView from "./McpView.vue";

const connection: McpConnection = {
  id: "mcp-1", name: "CLS", transport: "streamable_http", url: "https://example.test/mcp",
  enabled: true, timeoutSeconds: 30, retries: 1, lastCheck: "2026-08-20T00:00:00Z",
  lastError: null, discoveredTools: [{ name: "query_logs", description: "查询日志" }],
  createdAt: "2026-08-20T00:00:00Z", updatedAt: "2026-08-20T00:00:00Z",
};

beforeEach(() => setActivePinia(createPinia()));

describe("McpView", () => {
  it("初始化服务器 store 并展示真实工具与 URL 凭据警告", async () => {
    const store = useMcpStore();
    store.connections = [connection];
    store.initialize = vi.fn(async () => undefined);
    store.reset = vi.fn();
    const wrapper = mount(McpView);
    await flushPromises();

    expect(store.initialize).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("MCP Servers");
    expect(wrapper.text()).toContain("query_logs");
    expect(wrapper.text()).toContain("禁止将 token、secret 或 password 放入 URL query");
    expect(wrapper.get(".mcp-connection-list").attributes("aria-label")).toBe("MCP 连接列表");
  });

  it("连接列表和工具区域使用有界滚动布局", () => {
    const store = useMcpStore();
    store.connections = [connection];
    store.initialize = vi.fn(async () => undefined);
    const wrapper = mount(McpView);
    expect(wrapper.find(".mcp-connection-list").exists()).toBe(true);
    expect(wrapper.find(".mcp-tools").exists()).toBe(true);
  });
});
