<script setup lang="ts">
import { ref } from "vue";

import type { ChatMemoryMode, ChatSession } from "@super-ai/api-contracts";

const props = defineProps<{
  sessions: readonly ChatSession[];
  selectedSessionId: string | null;
  onSelect: (id: string) => Promise<void>;
}>();

const expandedSessionId = ref<string | null>(null);
const busyId = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

const KNOWN_HEADINGS: readonly string[] = [
  "对话目标",
  "关键事实与标识",
  "已做决定",
  "工具与证据",
  "未解决事项",
  "风险与注意事项",
];

interface SummarySection {
  title: string;
  content: string;
}

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

function parseSummary(text: string | null): SummarySection[] {
  if (!text?.trim()) return [];
  const rawSections: Array<{ title: string; lines: string[] }> = [];
  let current: { title: string; lines: string[] } | null = null;
  for (const line of text.split("\n")) {
    if (line.startsWith("## ")) {
      current = { title: line.slice(3).trim(), lines: [] };
      rawSections.push(current);
    } else if (current !== null) {
      current.lines.push(line);
    }
  }
  if (!rawSections.some((section) => KNOWN_HEADINGS.includes(section.title))) {
    return [{ title: "摘要", content: text.trim() }];
  }
  const map = new Map(
    rawSections.map((section) => [section.title, section.lines.join("\n").trim()]),
  );
  const sections: SummarySection[] = KNOWN_HEADINGS.map((title) => ({
    title,
    content: map.get(title) || "（无）",
  }));
  const unknown = rawSections.filter(
    (section) => !KNOWN_HEADINGS.includes(section.title),
  );
  if (unknown.length > 0) {
    sections.push({
      title: "其他",
      content: unknown
        .map((section) => `### ${section.title}\n${section.lines.join("\n").trim()}`)
        .join("\n\n"),
    });
  }
  return sections;
}

async function toggleSession(id: string): Promise<void> {
  if (expandedSessionId.value === id) {
    expandedSessionId.value = null;
    return;
  }
  const previous = expandedSessionId.value;
  busyId.value = id;
  errorMessage.value = null;
  try {
    if (id !== props.selectedSessionId) {
      await props.onSelect(id);
    }
    expandedSessionId.value = id;
  } catch (error: unknown) {
    expandedSessionId.value = previous;
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
      <p v-if="sessions.length === 0" class="muted">暂无会话</p>
      <template v-for="session in sessions" :key="session.id">
        <button
          type="button"
          class="summary-session"
          :class="{ 'is-selected': session.id === selectedSessionId }"
          :aria-expanded="session.id === expandedSessionId"
          :disabled="busyId !== null"
          @click="toggleSession(session.id)"
        >
          <strong>{{ session.title }}</strong>
          <small>
            {{ session.memorySummary ? `已压缩 ${session.compactedMessageCount} 条` : "未压缩" }}
          </small>
        </button>
        <article
          v-if="expandedSessionId === session.id"
          class="summary-card"
          aria-label="压缩摘要详情"
        >
          <header class="summary-card__head">
            <strong>压缩摘要</strong>
            <button type="button" aria-label="收起摘要" @click="expandedSessionId = null">收起</button>
          </header>
          <template v-if="session.memorySummary">
            <section
              v-for="section in parseSummary(session.memorySummary)"
              :key="section.title"
              class="summary-card__section"
            >
              <h4>{{ section.title }}</h4>
              <p>{{ section.content }}</p>
            </section>
            <dl class="summary-card__meta">
              <dt>记忆模式</dt>
              <dd>{{ modeLabel(session.memoryMode) }}</dd>
              <dt>已压缩</dt>
              <dd>{{ session.compactedMessageCount }} 条</dd>
              <dt>最近压缩</dt>
              <dd>{{ formatTime(session.lastCompactedAt) }}</dd>
            </dl>
          </template>
          <p v-else class="muted">尚未压缩</p>
        </article>
      </template>
    </div>
    <p v-if="errorMessage" class="field-error" role="alert">{{ errorMessage }}</p>
  </section>
</template>
