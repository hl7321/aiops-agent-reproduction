<script setup lang="ts">
import { LoaderCircle } from "lucide-vue-next";

withDefaults(defineProps<{ message?: string }>(), { message: "正在加载" });
</script>

<template>
  <section class="app-state" role="status" aria-live="polite">
    <LoaderCircle class="app-state__icon app-state__icon--spin" :size="24" aria-hidden="true" />
    <p>{{ message }}</p>
  </section>
</template>
