<script setup lang="ts">
import { Inbox } from "lucide-vue-next";

withDefaults(defineProps<{ title?: string; description?: string }>(), {
  title: "暂无内容",
  description: "这里还没有可显示的数据。",
});
</script>

<template>
  <section class="app-state" role="status" aria-live="polite">
    <Inbox class="app-state__icon" :size="26" aria-hidden="true" />
    <strong>{{ title }}</strong>
    <p>{{ description }}</p>
  </section>
</template>
