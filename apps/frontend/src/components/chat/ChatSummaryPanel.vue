<script setup lang="ts">
import { computed, ref } from "vue";

import type { ChatMemoryMode, ChatSession } from "@super-ai/api-contracts";

const props = defineProps<{
  sessions: readonly ChatSession[];
  selectedSessionId: string | null;
  onSelect: (id: string) => Promise<void>;
}>();

const busyId = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

const selectedSession = computed(
  () => props.sessions.find((session) => session.id === props.selectedSessionId) ?? null,
);

const MODE_LABELS: Record<ChatMemoryMode, string> = {
  every_30_turns: "每 30 轮压缩",
  context_70_percent: "上下文达到 70%",
  manual: "仅手动压缩",
};

function modeLabel(mode: ChatMemoryMode): string {
  return MODE_LABELS[mode];
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

async function selectSession(id: string): Promise<void> {
  if (busyId.value !== null) return;
  busyId.value = id;
  errorMessage.value = null;
  try {
    await props.onSelect(id);
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : "切换会话失败";
  } finally {
    busyId.value = null;
  }
}
</script>

<template>
  <section class="summary-panel" aria-label="压缩摘要">
    <header>
      <h3>压缩摘要</h3>
      <small>{{ sessions.length }} 个会话</small>
    </header>
    <div class="summary-list" role="list">
      <button
        v-for="session in sessions"
        :key="session.id"
        type="button"
        class="summary-session"
        :class="{ 'is-selected': session.id === selectedSessionId }"
        :aria-pressed="session.id === selectedSessionId"
        :disabled="busyId !== null"
        @click="selectSession(session.id)"
      >
        <strong>{{ session.title }}</strong>
        <small>
          {{ session.memorySummary ? `已压缩 ${session.compactedMessageCount} 条` : "未压缩" }}
        </small>
      </button>
    </div>
    <div v-if="selectedSession" class="summary-detail">
      <template v-if="selectedSession.memorySummary">
        <p class="summary-text">{{ selectedSession.memorySummary }}</p>
        <dl>
          <dt>记忆模式</dt>
          <dd>{{ modeLabel(selectedSession.memoryMode) }}</dd>
          <dt>已压缩</dt>
          <dd>{{ selectedSession.compactedMessageCount }} 条</dd>
          <dt>最近压缩</dt>
          <dd>{{ formatTime(selectedSession.lastCompactedAt) }}</dd>
        </dl>
      </template>
      <p v-else class="muted">尚未压缩</p>
    </div>
    <p v-else class="muted">暂无会话</p>
    <p v-if="errorMessage" class="field-error" role="alert">{{ errorMessage }}</p>
  </section>
</template>
