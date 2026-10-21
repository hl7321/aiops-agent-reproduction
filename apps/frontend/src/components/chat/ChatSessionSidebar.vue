<script setup lang="ts">
import { Pencil, Plus, Trash2 } from "lucide-vue-next";
import { onMounted, ref } from "vue";

import type { ChatSession } from "@super-ai/api-contracts";

import { useChatStore } from "../../stores/chat";

const chat = useChatStore();
const deleteCandidate = ref<string | null>(null);
const busy = ref(false);
const editingId = ref<string | null>(null);
const draftTitle = ref("");
const renameError = ref<string | null>(null);

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

function startRename(session: ChatSession): void {
  editingId.value = session.id;
  draftTitle.value = session.title;
  renameError.value = null;
}

function cancelRename(): void {
  editingId.value = null;
  draftTitle.value = "";
  renameError.value = null;
}

async function saveRename(sessionId: string): Promise<void> {
  const title = draftTitle.value.trim();
  if (!title) {
    renameError.value = "标题不能为空";
    return;
  }
  if (title.length > 128) {
    renameError.value = "标题最多 128 个字符";
    return;
  }
  busy.value = true;
  renameError.value = null;
  try {
    await chat.renameSession(sessionId, title);
    cancelRename();
  } catch (error: unknown) {
    renameError.value = error instanceof Error ? error.message : "重命名失败";
  } finally {
    busy.value = false;
  }
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
      <div
        v-for="session in chat.sessions"
        :key="session.id"
        class="conversation-list__row"
      >
        <form
          v-if="editingId === session.id"
          class="conversation-rename"
          @submit.prevent="saveRename(session.id)"
        >
          <input
            v-model="draftTitle"
            :maxlength="128"
            aria-label="会话标题"
            @keydown.esc="cancelRename"
          />
          <div class="conversation-rename__actions">
            <button type="submit" :disabled="busy">保存</button>
            <button type="button" :disabled="busy" @click="cancelRename">取消</button>
          </div>
          <p v-if="renameError" class="field-error" role="alert">{{ renameError }}</p>
        </form>
        <template v-else>
          <button
            type="button"
            class="conversation-list__item"
            :class="{ 'conversation-list__item--active': chat.selectedDetail?.session.id === session.id }"
            @click="chat.selectSession(session.id)"
          >
            <span>{{ session.title }}</span><time>{{ new Date(session.updatedAt).toLocaleString("zh-CN") }}</time>
          </button>
          <button
            type="button"
            class="conversation-list__edit"
            :disabled="busy"
            aria-label="重命名会话"
            @click.stop="startRename(session)"
          >
            <Pencil :size="14" aria-hidden="true" />
          </button>
        </template>
      </div>
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
