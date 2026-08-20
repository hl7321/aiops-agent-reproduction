<script setup lang="ts">
import { Send } from "lucide-vue-next";
import { ref } from "vue";

const props = defineProps<{
  disabled?: boolean;
  onSend: (content: string) => Promise<void>;
}>();

const draft = ref("");
const composing = ref(false);
const submitting = ref(false);
const errorMessage = ref<string | null>(null);

async function submit(): Promise<void> {
  const content = draft.value.trim();
  if (!content || props.disabled === true || submitting.value) return;
  submitting.value = true;
  errorMessage.value = null;
  try {
    await props.onSend(content);
    draft.value = "";
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : "消息发送失败";
  } finally {
    submitting.value = false;
  }
}

async function onKeydown(event: KeyboardEvent): Promise<void> {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing || composing.value) return;
  event.preventDefault();
  await submit();
}
</script>

<template>
  <form class="chat-composer" aria-label="发送消息" @submit.prevent="submit">
    <textarea
      v-model="draft"
      rows="3"
      style="resize: none"
      aria-label="消息内容"
      placeholder="输入问题，Enter 发送，Shift+Enter 换行"
      :disabled="disabled || submitting"
      @compositionstart="composing = true"
      @compositionend="composing = false"
      @keydown="onKeydown"
    />
    <button class="button button--primary chat-composer__send" type="submit" :disabled="disabled || submitting || !draft.trim()">
      <Send :size="17" aria-hidden="true" />{{ submitting ? "发送中" : "发送" }}
    </button>
    <p v-if="errorMessage" class="field-error" role="alert">{{ errorMessage }}</p>
  </form>
</template>
