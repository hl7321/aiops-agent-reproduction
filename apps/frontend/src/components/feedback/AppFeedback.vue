<script setup lang="ts">
import { CircleCheck, CircleX, Info, X } from "lucide-vue-next";
import { computed, onBeforeUnmount, watch } from "vue";

import { useFeedbackStore } from "../../stores/feedback";

const feedback = useFeedbackStore();
let timer: ReturnType<typeof setTimeout> | undefined;

const icon = computed(() => {
  if (feedback.current?.kind === "success") return CircleCheck;
  if (feedback.current?.kind === "error") return CircleX;
  return Info;
});

function clearTimer(): void {
  if (timer !== undefined) {
    clearTimeout(timer);
    timer = undefined;
  }
}

watch(
  () => feedback.current?.id,
  (id) => {
    clearTimer();
    if (id !== undefined) {
      timer = setTimeout(() => feedback.close(), 3_000);
    }
  },
  { flush: "sync" },
);

onBeforeUnmount(clearTimer);
</script>

<template>
  <Transition name="feedback">
    <aside
      v-if="feedback.current"
      class="app-feedback"
      :class="`app-feedback--${feedback.current.kind}`"
      :role="feedback.current.kind === 'error' ? 'alert' : 'status'"
      :aria-live="feedback.current.kind === 'error' ? 'assertive' : 'polite'"
    >
      <component :is="icon" :size="19" aria-hidden="true" />
      <span>{{ feedback.current.message }}</span>
      <button type="button" aria-label="关闭提示" @click="feedback.close">
        <X :size="17" aria-hidden="true" />
      </button>
    </aside>
  </Transition>
</template>
