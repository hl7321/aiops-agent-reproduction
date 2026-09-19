<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  FEEDBACK_REASONS,
  type FeedbackRating,
  type FeedbackReason,
  type FeedbackTargetType,
  type UserFeedback,
  type UserFeedbackUpsertRequest,
} from "@super-ai/api-contracts";

import { useUserFeedbackStore } from "../../stores/userFeedback";

const props = withDefaults(defineProps<{
  targetType: FeedbackTargetType;
  targetId: string;
  subjectId?: string | null;
  load?: () => Promise<UserFeedback | undefined>;
  save?: (body: UserFeedbackUpsertRequest) => Promise<void>;
  remove?: (item: UserFeedback) => Promise<void>;
}>(), { subjectId: null });

const store = useUserFeedbackStore();
const existing = ref<UserFeedback | null>(null);
const rating = ref<FeedbackRating | null>(null);
const reason = ref<FeedbackReason | "">("");
const comment = ref("");
const correction = ref("");
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const savedMessage = ref<string | null>(null);

function apply(item: UserFeedback | undefined): void {
  existing.value = item ?? null;
  rating.value = item?.rating ?? null;
  reason.value = item?.reason ?? "";
  comment.value = item?.comment ?? "";
  correction.value = item?.correction ?? "";
}

onMounted(async () => {
  try {
    if (props.load !== undefined) apply(await props.load());
    else {
      await store.load(props.targetType, props.targetId);
      apply(store.find(props.targetType, props.targetId, props.subjectId));
    }
  } catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : "反馈恢复失败";
  } finally {
    loading.value = false;
  }
});

function choose(value: FeedbackRating): void {
  rating.value = value;
  savedMessage.value = null;
}

async function submit(): Promise<void> {
  if (rating.value === null) {
    error.value = "请先选择赞同或反对";
    return;
  }
  error.value = null;
  savedMessage.value = null;
  saving.value = true;
  const body: UserFeedbackUpsertRequest = {
    targetType: props.targetType,
    targetId: props.targetId,
    subjectId: props.subjectId,
    rating: rating.value,
    reason: reason.value || null,
    comment: comment.value,
    correction: correction.value,
  };
  try {
    if (props.save !== undefined) await props.save(body);
    else existing.value = await store.save(body);
    savedMessage.value = "反馈已保存";
  } catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : "反馈保存失败";
  } finally {
    saving.value = false;
  }
}

async function deleteFeedback(): Promise<void> {
  const item = existing.value;
  if (item === null) return;
  error.value = null;
  saving.value = true;
  try {
    if (props.remove !== undefined) await props.remove(item);
    else await store.remove(item);
    apply(undefined);
    savedMessage.value = "反馈已删除";
  } catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : "反馈删除失败";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <details class="user-feedback-control">
    <!-- 折起来的时候也要能看出"反馈已经存下来了"，否则点完保存不知道存到哪去了。 -->
    <summary>反馈{{ existing === null ? "" : existing.rating === "positive" ? " · 已赞同" : " · 已反对" }}</summary>
    <p v-if="loading" role="status">正在恢复反馈</p>
    <form v-else @submit.prevent="submit">
      <div class="feedback-rating" aria-label="回答评价">
        <button type="button" aria-label="赞同" :aria-pressed="rating === 'positive'" @click="choose('positive')">赞同</button>
        <button type="button" aria-label="反对" :aria-pressed="rating === 'negative'" @click="choose('negative')">反对</button>
      </div>
      <label>问题类型<select v-model="reason"><option value="">未选择</option><option v-for="item in FEEDBACK_REASONS" :key="item" :value="item">{{ item }}</option></select></label>
      <label>评论<textarea v-model="comment" name="feedback-comment" maxlength="2000" /></label>
      <label>建议纠正<textarea v-model="correction" name="feedback-correction" maxlength="4000" /></label>
      <div class="feedback-actions">
        <button type="submit" :disabled="saving">{{ existing ? "更新反馈" : "保存反馈" }}</button>
        <button v-if="existing" type="button" data-action="delete-feedback" :disabled="saving" @click="deleteFeedback">删除反馈</button>
      </div>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-else-if="savedMessage" role="status">{{ savedMessage }}</p>
    </form>
  </details>
</template>

<style scoped>
.user-feedback-control { margin-top: 8px; font-size: 11px; }.user-feedback-control summary { color: var(--color-accent); cursor: pointer; }.user-feedback-control form { display: grid; gap: 7px; margin-top: 7px; padding: 9px; border: 1px solid var(--color-border); border-radius: 8px; background: #f8faf9; }.feedback-rating,.feedback-actions { display: flex; gap: 6px; }.feedback-rating button[aria-pressed="true"] { border-color: var(--color-accent); background: var(--color-accent-soft); }.user-feedback-control label { display: grid; gap: 3px; color: var(--color-text-muted); }.user-feedback-control select,.user-feedback-control textarea { width: 100%; border: 1px solid var(--color-border); border-radius: 6px; padding: 6px; background: white; color: var(--color-text); font: inherit; }.user-feedback-control textarea { min-height: 52px; resize: vertical; }.user-feedback-control button { min-height: 28px; border: 1px solid var(--color-border); border-radius: 6px; padding: 4px 8px; background: white; cursor: pointer; }.user-feedback-control [role="alert"] { margin: 0; color: var(--color-danger); }
</style>
