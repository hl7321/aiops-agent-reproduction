<script setup lang="ts">
import { Plus, Trash2 } from "lucide-vue-next";
import { onMounted, ref } from "vue";

import { useChatStore } from "../../stores/chat";

const chat = useChatStore();
const deleteCandidate = ref<string | null>(null);
const busy = ref(false);

onMounted(async () => {
  try { await chat.ensureActiveSession(); }
  catch { /* Store exposes its safe loading error. */ }
});

async function create(): Promise<void> {
  busy.value = true;
  try { await chat.createSession(); } finally { busy.value = false; }
}

async function remove(): Promise<void> {
  const id = deleteCandidate.value;
  if (id === null) return;
  busy.value = true;
  try {
    await chat.deleteSession(id);
    deleteCandidate.value = null;
  } finally { busy.value = false; }
}
</script>

<template>
  <aside class="conversation-panel" aria-label="会话区域">
    <div class="conversation-panel__header">
      <div><p class="eyebrow">CONVERSATIONS</p><h2>会话</h2></div>
      <button class="icon-button" type="button" :disabled="busy" aria-label="新建会话" @click="create">
        <Plus :size="18" aria-hidden="true" />
      </button>
    </div>
    <p v-if="chat.errorMessage" class="field-error" role="alert">{{ chat.errorMessage }}</p>
    <nav class="conversation-list" aria-label="Chat 会话列表">
      <button
        v-for="session in chat.sessions"
        :key="session.id"
        type="button"
        class="conversation-list__item"
        :class="{ 'conversation-list__item--active': chat.selectedDetail?.session.id === session.id }"
        @click="chat.selectSession(session.id)"
      >
        <span>{{ session.title }}</span><time>{{ new Date(session.updatedAt).toLocaleString("zh-CN") }}</time>
      </button>
    </nav>
    <button
      v-if="chat.selectedDetail"
      class="conversation-delete"
      type="button"
      @click="deleteCandidate = chat.selectedDetail.session.id"
    ><Trash2 :size="15" aria-hidden="true" />删除当前会话</button>
    <div v-if="deleteCandidate" class="inline-confirm" role="dialog" aria-label="确认删除会话">
      <p>删除后会同时移除该会话的服务端消息，确定继续？</p>
      <button type="button" @click="deleteCandidate = null">取消</button>
      <button type="button" :disabled="busy" @click="remove">确认删除</button>
    </div>
  </aside>
</template>
