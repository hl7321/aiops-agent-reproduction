<script setup lang="ts">
import { MessageSquareText } from "lucide-vue-next";

import AppEmptyState from "../components/states/AppEmptyState.vue";
</script>

<template>
  <section class="route-placeholder" data-route-canvas="chat" aria-labelledby="chat-canvas-title">
    <div class="route-placeholder__icon"><MessageSquareText :size="26" aria-hidden="true" /></div>
    <p class="eyebrow">CHAT WORKSPACE</p>
    <h2 id="chat-canvas-title">对话能力尚未接入</h2>
    <p>当前已建立认证工作台与会话区域边界，真实 Chat 流程将在后续提案实现。</p>
    <AppEmptyState title="暂无会话内容" description="完成后续 Chat 提案后，这里将显示真实对话。" />
  </section>
</template>
