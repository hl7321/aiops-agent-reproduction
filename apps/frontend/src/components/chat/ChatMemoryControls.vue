<script setup lang="ts">
import { ref } from "vue";

import type { ChatMemoryMode, ChatSession } from "@super-ai/api-contracts";

const props = defineProps<{
  session: ChatSession;
  onUpdate: (mode: ChatMemoryMode) => Promise<void>;
  onCompact: () => Promise<void>;
}>();

const busy = ref(false);
const errorMessage = ref<string | null>(null);

async function update(event: Event): Promise<void> {
  const mode = (event.target as HTMLSelectElement).value as ChatMemoryMode;
  await run(() => props.onUpdate(mode));
}

async function compact(): Promise<void> {
  await run(props.onCompact);
}

async function run(operation: () => Promise<void>): Promise<void> {
  busy.value = true;
  errorMessage.value = null;
  try {
    await operation();
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : "记忆操作失败";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="memory-controls" aria-label="会话记忆设置">
    <label>记忆模式
      <select :value="session.memoryMode" :disabled="busy" @change="update">
        <option value="every_30_turns">每 30 轮压缩</option>
        <option value="context_70_percent">上下文达到 70%</option>
        <option value="manual">仅手动压缩</option>
      </select>
    </label>
    <div class="memory-usage">
      <span>上下文 {{ session.contextUsagePercent.toFixed(1) }}%</span>
      <progress :value="session.contextTokens" :max="session.contextWindowTokens">
        {{ session.contextUsagePercent.toFixed(1) }}%
      </progress>
    </div>
    <button class="button memory-controls__compact" type="button" :disabled="busy || !session.canCompact" @click="compact">
      手动压缩
    </button>
    <p v-if="errorMessage" class="field-error" role="alert">{{ errorMessage }}</p>
  </div>
</template>
