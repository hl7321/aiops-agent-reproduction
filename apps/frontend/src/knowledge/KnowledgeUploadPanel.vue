<script setup lang="ts">
import { FileUp } from "lucide-vue-next";
import { computed, ref } from "vue";

import type { ChunkingConfig, ChunkingStrategy } from "@super-ai/api-contracts";
import { KNOWLEDGE_UPLOAD_POLICY } from "@super-ai/api-contracts";

defineProps<{ busy: boolean }>();
const emit = defineEmits<{
  upload: [file: File, config: ChunkingConfig];
}>();

const strategy = ref<ChunkingStrategy>("fixed-character");
const maxCharacters = ref(1_200);
const overlap = ref(200);
const selectedFile = ref<File | null>(null);
const errorMessage = ref<string | null>(null);
const accept = computed(() => Object.keys(KNOWLEDGE_UPLOAD_POLICY.allowedTypes).join(","));
const GENERIC_BINARY_MIME = "application/octet-stream";

function selectFile(event: Event): void {
  const input = event.currentTarget as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  errorMessage.value = validateFile(file);
  selectedFile.value = errorMessage.value === null && file !== null ? normalizeMime(file) : null;
}

function submit(): void {
  errorMessage.value = validateFile(selectedFile.value);
  if (errorMessage.value !== null || selectedFile.value === null) return;
  if (strategy.value === "fixed-character") {
    if (!Number.isInteger(maxCharacters.value) || maxCharacters.value <= 0) {
      errorMessage.value = "分段长度必须是正整数。";
      return;
    }
    if (!Number.isInteger(overlap.value) || overlap.value < 0
      || overlap.value >= maxCharacters.value) {
      errorMessage.value = "重叠长度必须小于分段长度，且不能为负数。";
      return;
    }
    emit("upload", selectedFile.value, {
      strategy: "fixed-character",
      maxCharacters: maxCharacters.value,
      overlap: overlap.value,
    });
    return;
  }
  emit("upload", selectedFile.value, { strategy: strategy.value });
}

function validateFile(file: File | null): string | null {
  if (file === null) return "请选择 Markdown 或 PDF 文档。";
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const allowed = KNOWLEDGE_UPLOAD_POLICY.allowedTypes;
  if (!(extension in allowed)) {
    return "只支持 Markdown 与 PDF 文件，请检查扩展名和 MIME 类型。";
  }
  const expectedMime = allowed[extension as keyof typeof allowed];
  if (file.type !== expectedMime && !isNormalizableMime(extension, file.type)) {
    return "只支持 Markdown 与 PDF 文件，请检查扩展名和 MIME 类型。";
  }
  if (file.size > KNOWLEDGE_UPLOAD_POLICY.maxBytes) return "文件不能超过 10 MiB。";
  return null;
}

function normalizeMime(file: File): File {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const expectedMime = KNOWLEDGE_UPLOAD_POLICY.allowedTypes[
    extension as keyof typeof KNOWLEDGE_UPLOAD_POLICY.allowedTypes
  ];
  if (file.type === expectedMime) return file;
  return new File([file], file.name, { type: expectedMime, lastModified: file.lastModified });
}

function isNormalizableMime(extension: string, mimeType: string): boolean {
  return mimeType === "" || mimeType === GENERIC_BINARY_MIME
    || (extension === ".md" && mimeType === "text/x-markdown");
}
</script>

<template>
  <section class="knowledge-upload" aria-labelledby="knowledge-upload-title">
    <div>
      <p class="eyebrow">UPLOAD</p>
      <h2 id="knowledge-upload-title">上传与切分</h2>
      <p>支持 UTF-8 Markdown 和 PDF，单个文件最大 10 MiB。</p>
    </div>
    <form class="knowledge-upload__form" @submit.prevent="submit">
      <label class="file-picker">
        <span>选择文档</span>
        <input type="file" :accept="accept" :disabled="busy" @change="selectFile">
      </label>
      <label>
        <span>切分策略</span>
        <select v-model="strategy" :disabled="busy">
          <option value="fixed-character">固定字符</option>
          <option value="markdown-heading">Markdown 标题</option>
          <option value="paragraph">自然段落</option>
        </select>
      </label>
      <template v-if="strategy === 'fixed-character'">
        <label>
          <span>分段长度</span>
          <input v-model.number="maxCharacters" name="maxCharacters" type="number" min="1" :disabled="busy">
        </label>
        <label>
          <span>重叠长度</span>
          <input v-model.number="overlap" name="overlap" type="number" min="0" :disabled="busy">
        </label>
      </template>
      <button class="button button--primary" type="submit" :disabled="busy">
        <FileUp :size="17" aria-hidden="true" />
        {{ busy ? "正在上传" : "上传并开始索引" }}
      </button>
    </form>
    <p v-if="errorMessage" class="knowledge-form-error" role="alert">{{ errorMessage }}</p>
  </section>
</template>

<style scoped>
.knowledge-upload { border: 1px solid var(--color-border); border-radius: var(--radius-md); display: grid; grid-template-columns: minmax(220px, .7fr) minmax(560px, 1.3fr); gap: var(--space-6); padding: var(--space-5); background: var(--color-surface); }
.knowledge-upload h2 { margin: 5px 0 8px; font-size: 20px; }
.knowledge-upload p { margin: 0; color: var(--color-text-muted); font-size: 13px; line-height: 1.6; }
.knowledge-upload__form { display: grid; grid-template-columns: minmax(180px, 1.4fr) repeat(3, minmax(120px, .8fr)) auto; align-items: end; gap: var(--space-3); }
.knowledge-upload__form label { min-width: 0; display: grid; gap: 6px; color: var(--color-text-muted); font-size: 12px; font-weight: 700; }
.knowledge-upload__form input, .knowledge-upload__form select { min-width: 0; height: 42px; border: 1px solid var(--color-border-strong); border-radius: var(--radius-sm); padding: 0 10px; background: var(--color-surface-subtle); }
.file-picker input { padding: 8px; }
.knowledge-form-error { grid-column: 1 / -1; color: var(--color-danger) !important; }
</style>
