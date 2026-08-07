<script setup lang="ts">
import { publicConfig } from "./config";
</script>

<template>
  <main class="shell">
    <header>
      <p class="eyebrow">DESKTOP WEB FOUNDATION</p>
      <h1>{{ publicConfig.title }}</h1>
    </header>
    <RouterView />
  </main>
</template>

<style>
:root {
  color: #172033;
  background: #f3f6fb;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
}

body {
  margin: 0;
  min-width: 1024px;
}

.shell {
  width: min(1120px, calc(100% - 96px));
  margin: 0 auto;
  padding: 72px 0;
}

.eyebrow {
  margin: 0 0 12px;
  color: #4967d1;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

h1 {
  margin: 0 0 32px;
  font-size: 42px;
}
</style>
