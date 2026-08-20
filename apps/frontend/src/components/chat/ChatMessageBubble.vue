<script setup lang="ts">
import { computed } from "vue";

import type { AgentToolCallAudit, ChatMessage } from "@super-ai/api-contracts";

import { renderSafeMarkdown } from "../../chat/renderSafeMarkdown";
import ChatCitationList from "./ChatCitationList.vue";
import ChatToolActivity from "./ChatToolActivity.vue";

const props = withDefaults(defineProps<{
  message: ChatMessage;
  audits?: readonly AgentToolCallAudit[];
}>(), { audits: () => [] });
const renderedContent = computed(() => renderSafeMarkdown(props.message.content));
const messageAudits = computed(() => {
  const ids = new Set(props.message.metadata.toolCallIds ?? []);
  return props.audits.filter((audit) => ids.has(audit.toolCallId));
});
</script>

<template>
  <article class="chat-message" :class="`chat-message--${message.role}`">
    <p class="chat-message__role">{{ message.role === "user" ? "你" : "Agent" }}</p>
    <div class="chat-message__bubble">
      <!-- 内容已经由 marked 解析并经 DOMPurify allowlist 清洗。 -->
      <div class="markdown-body" v-html="renderedContent" />
      <ChatToolActivity
        v-if="message.role === 'assistant' && messageAudits.length"
        reasoning=""
        :live-tool-calls="{}"
        :audits="messageAudits"
      />
      <ChatCitationList
        v-if="message.role === 'assistant'"
        :references="message.metadata.references ?? []"
      />
    </div>
  </article>
</template>
