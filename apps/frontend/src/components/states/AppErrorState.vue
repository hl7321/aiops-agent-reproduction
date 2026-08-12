<script setup lang="ts">
import { CircleAlert } from "lucide-vue-next";

withDefaults(defineProps<{ title?: string; message: string }>(), { title: "出现问题" });
</script>

<template>
  <section class="app-state app-state--error" role="alert">
    <CircleAlert class="app-state__icon" :size="26" aria-hidden="true" />
    <strong>{{ title }}</strong>
    <p>{{ message }}</p>
  </section>
</template>
