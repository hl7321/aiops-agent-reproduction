<script setup lang="ts">
import { computed } from "vue";

type AsyncStatus = "idle" | "loading" | "success" | "error";

const props = defineProps<{ status: AsyncStatus; label?: string }>();
const labels: Record<AsyncStatus, string> = {
  idle: "待连接",
  loading: "连接中",
  success: "可用",
  error: "异常",
};
const text = computed(() => props.label ?? labels[props.status]);
</script>

<template>
  <span class="async-status" :class="`async-status--${status}`" role="status">
    <span class="async-status__dot" aria-hidden="true" />
    {{ text }}
  </span>
</template>
