<script setup lang="ts">
import { Blocks } from "lucide-vue-next";

defineProps<{ capability: string }>();
</script>

<template>
  <section class="route-placeholder" :data-route-canvas="capability.toLowerCase()">
    <div class="route-placeholder__icon"><Blocks :size="26" aria-hidden="true" /></div>
    <p class="eyebrow">CAPABILITY PLACEHOLDER</p>
    <h2>{{ capability }} 工作区</h2>
    <p>{{ capability }} 产品能力将在后续提案实现。当前页面仅验证工作台路由与布局边界。</p>
  </section>
</template>
