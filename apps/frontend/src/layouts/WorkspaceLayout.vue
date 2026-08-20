<script setup lang="ts">
import {
  Bot,
  BrainCircuit,
  ChevronDown,
  Database,
  LogOut,
  MessageSquareText,
  PanelLeft,
} from "lucide-vue-next";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import AsyncStatusBadge from "../components/states/AsyncStatusBadge.vue";
import ChatSessionSidebar from "../components/chat/ChatSessionSidebar.vue";
import { useAuthStore } from "../stores/auth";
import { useFeedbackStore } from "../stores/feedback";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const feedback = useFeedbackStore();
const title = computed(() => route.meta.title ?? "工作台");
const showConversationPanel = computed(() => route.meta.showConversationPanel === true);

const navigation = [
  { to: "/chat", label: "Chat", icon: MessageSquareText },
  { to: "/knowledge", label: "知识库", icon: Database },
  { to: "/aiops", label: "AIOps", icon: BrainCircuit },
  { to: "/mcp", label: "MCP", icon: Bot },
] as const;

async function logout(): Promise<void> {
  try {
    await auth.logout();
    feedback.show("success", "已安全退出");
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? `服务端撤销失败：${error.message}` : "退出失败");
  } finally {
    await router.replace("/login");
  }
}
</script>

<template>
  <div class="workspace" :class="{ 'workspace--with-conversations': showConversationPanel }">
    <aside class="workspace-rail">
      <RouterLink class="workspace-brand" to="/chat" aria-label="返回 Chat">
        <PanelLeft :size="22" aria-hidden="true" />
      </RouterLink>
      <nav class="rail-nav" aria-label="主导航">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to" :aria-label="item.label">
          <component :is="item.icon" :size="21" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="rail-account">
        <span class="account-avatar" aria-hidden="true">{{ auth.user?.email.slice(0, 1).toUpperCase() }}</span>
        <span class="sr-only">当前账号 {{ auth.user?.email }}</span>
      </div>
    </aside>

    <ChatSessionSidebar v-if="showConversationPanel" />

    <section class="workspace-content">
      <header class="workspace-topbar">
        <div>
          <p class="workspace-topbar__context">智能 OnCall 工作台</p>
          <h1>{{ title }}</h1>
        </div>
        <div class="workspace-topbar__actions">
          <div class="service-status" aria-label="服务状态">
            <span>服务状态</span>
            <AsyncStatusBadge status="idle" label="待检测" />
          </div>
          <div class="account-menu">
            <button class="account-button" type="button" aria-label="账号菜单">
              <span class="account-avatar">{{ auth.user?.email.slice(0, 1).toUpperCase() }}</span>
              <span>{{ auth.user?.email }}</span>
              <ChevronDown :size="16" aria-hidden="true" />
            </button>
            <button class="icon-button" type="button" aria-label="退出登录" @click="logout">
              <LogOut :size="18" aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>
      <main class="route-canvas"><RouterView /></main>
    </section>
  </div>
</template>
