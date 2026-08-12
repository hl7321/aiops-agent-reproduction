import { defineStore } from "pinia";
import { ref } from "vue";

export type FeedbackKind = "success" | "info" | "error";

export interface FeedbackMessage {
  id: number;
  kind: FeedbackKind;
  message: string;
}

export const useFeedbackStore = defineStore("feedback", () => {
  const current = ref<FeedbackMessage | null>(null);
  let nextId = 1;

  function show(kind: FeedbackKind, message: string): void {
    current.value = { id: nextId, kind, message };
    nextId += 1;
  }

  function close(): void {
    current.value = null;
  }

  return { current, show, close };
});
