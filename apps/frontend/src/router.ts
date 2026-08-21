import type { RouterHistory } from "vue-router";
import { createRouter, createWebHistory } from "vue-router";

import WorkspaceLayout from "./layouts/WorkspaceLayout.vue";
import type { AuthStatus } from "./stores/auth";
import AiopsView from "./views/AiopsView.vue";
import ChatView from "./views/ChatView.vue";
import KnowledgeView from "./views/KnowledgeView.vue";
import LoginView from "./views/LoginView.vue";
import McpView from "./views/McpView.vue";
import RegisterView from "./views/RegisterView.vue";

declare module "vue-router" {
  interface RouteMeta {
    publicOnly?: boolean;
    requiresAuth?: boolean;
    showConversationPanel?: boolean;
    title?: string;
  }
}

export interface RouterAuth {
  status: AuthStatus;
  initialize(): Promise<void>;
}

export function createAppRouter(auth: RouterAuth, history: RouterHistory = createWebHistory()) {
  const router = createRouter({
    history,
    routes: [
      { path: "/", redirect: "/chat" },
      {
        path: "/login",
        name: "login",
        component: LoginView,
        meta: { publicOnly: true, title: "登录" },
      },
      {
        path: "/register",
        name: "register",
        component: RegisterView,
        meta: { publicOnly: true, title: "注册" },
      },
      {
        path: "/",
        component: WorkspaceLayout,
        meta: { requiresAuth: true },
        children: [
          {
            path: "chat",
            name: "chat",
            component: ChatView,
            meta: { title: "Chat", showConversationPanel: true },
          },
          {
            path: "knowledge",
            name: "knowledge",
            component: KnowledgeView,
            meta: { title: "知识库" },
          },
          {
            path: "aiops",
            name: "aiops",
            component: AiopsView,
            meta: { title: "AIOps" },
          },
          {
            path: "mcp",
            name: "mcp",
            component: McpView,
            meta: { title: "MCP" },
          },
        ],
      },
      { path: "/:pathMatch(.*)*", redirect: "/chat" },
    ],
  });

  let initialization: Promise<void> | undefined;
  router.beforeEach(async (to) => {
    initialization ??= auth.initialize();
    await initialization;
    const authenticated = auth.status === "authenticated";

    if (to.meta.publicOnly === true && authenticated) {
      return { name: "chat" };
    }
    if (to.matched.some((record) => record.meta.requiresAuth === true) && !authenticated) {
      return { name: "login", query: { redirect: to.fullPath } };
    }
    return true;
  });
  return router;
}

export function resolveSafeRedirect(value: unknown): string {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return "/chat";
  }
  return value;
}
