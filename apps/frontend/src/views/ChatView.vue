<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import type { ChatMessage } from "@super-ai/api-contracts";

import ChatComposer from "../components/chat/ChatComposer.vue";
import ChatConfigurationSidebar from "../components/chat/ChatConfigurationSidebar.vue";
import ChatMemoryControls from "../components/chat/ChatMemoryControls.vue";
import ChatMessageBubble from "../components/chat/ChatMessageBubble.vue";
import ChatCitationList from "../components/chat/ChatCitationList.vue";
import ChatToolActivity from "../components/chat/ChatToolActivity.vue";
import { useChatStore } from "../stores/chat";
import { useChatConfigurationStore } from "../stores/chatConfiguration";

const chat = useChatStore();
const configuration = useChatConfigurationStore();
const initializationError = ref<string | null>(null);
const isStreaming = computed(() => chat.liveStatus === "streaming");
const liveMessage = computed<ChatMessage>(() => ({
  id: "live-assistant",
  sessionId: chat.selectedDetail?.session.id ?? "live",
  role: "assistant",
  content: chat.liveContent,
  sequence: Number.MAX_SAFE_INTEGER,
  metadata: {},
  createdAt: new Date().toISOString(),
}));

onMounted(async () => {
  try {
    await Promise.all([chat.ensureActiveSession(), configuration.initialize()]);
  } catch (error: unknown) {
    initializationError.value = error instanceof Error ? error.message : "Chat 工作区加载失败";
  }
});

async function send(content: string): Promise<void> {
  await chat.streamMessage({ content });
}
</script>

<template>
  <section class="chat-workspace" data-route-canvas="chat" aria-label="Chat 工作区">
    <div class="chat-main">
      <div class="chat-transcript" aria-label="会话消息" aria-live="polite">
        <p v-if="initializationError" class="field-error" role="alert">{{ initializationError }}</p>
        <ChatMessageBubble
          v-for="message in chat.selectedDetail?.messages ?? []"
          :key="message.id"
          :message="message"
          :audits="chat.toolAudits"
        />
        <div v-if="isStreaming || chat.liveStatus === 'error'" class="live-turn">
          <ChatToolActivity
            :reasoning="chat.liveReasoning"
            :live-tool-calls="chat.liveToolCalls"
            :audits="[]"
          />
          <ChatMessageBubble
            v-if="chat.liveContent"
            :message="liveMessage"
            :feedback-enabled="false"
          />
          <ChatCitationList :references="chat.liveReferences" />
          <p v-if="chat.liveErrorMessage" class="field-error" role="alert">{{ chat.liveErrorMessage }}</p>
        </div>
      </div>
      <div v-if="chat.selectedDetail" class="chat-compose-zone">
        <ChatMemoryControls
          :session="chat.selectedDetail.session"
          :on-update="chat.updateMemoryMode"
          :on-compact="chat.compactMemory"
        />
        <ChatComposer :disabled="isStreaming" :on-send="send" />
      </div>
    </div>
    <ChatConfigurationSidebar />
  </section>
</template>
