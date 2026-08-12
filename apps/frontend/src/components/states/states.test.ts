// @vitest-environment happy-dom
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AppEmptyState from "./AppEmptyState.vue";
import AppErrorState from "./AppErrorState.vue";
import AppLoadingState from "./AppLoadingState.vue";
import AsyncStatusBadge from "./AsyncStatusBadge.vue";

describe("共享状态组件", () => {
  it("loading、empty 和 error 都有可见中文文字与 ARIA 语义", () => {
    const loading = mount(AppLoadingState, { props: { message: "正在恢复认证" } });
    const empty = mount(AppEmptyState, { props: { title: "暂无会话" } });
    const error = mount(AppErrorState, { props: { message: "加载失败" } });

    expect(loading.get('[role="status"]').text()).toContain("正在恢复认证");
    expect(empty.get('[role="status"]').text()).toContain("暂无会话");
    expect(error.get('[role="alert"]').text()).toContain("加载失败");
  });

  it.each([
    ["idle", "待连接"],
    ["loading", "连接中"],
    ["success", "可用"],
    ["error", "异常"],
  ] as const)("async status %s 同时显示文字", (status, label) => {
    const wrapper = mount(AsyncStatusBadge, { props: { status } });
    expect(wrapper.get('[role="status"]').text()).toContain(label);
  });
});
