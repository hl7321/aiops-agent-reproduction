<script setup lang="ts">
import { ref } from "vue";

import { useChatConfigurationStore } from "../../stores/chatConfiguration";
import { useFeedbackStore } from "../../stores/feedback";

const configuration = useChatConfigurationStore();
const feedback = useFeedbackStore();
const promptLabel = ref("");
const promptContent = ref("");
const editingPromptId = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

async function selectPrompt(event: Event): Promise<void> {
  const value = (event.target as HTMLSelectElement).value || null;
  await safe(() => configuration.updateSelection(value, configuration.selectedSkillIds));
}

async function toggleSkill(id: string, event: Event): Promise<void> {
  const checked = (event.target as HTMLInputElement).checked;
  const selected = checked
    ? [...configuration.selectedSkillIds, id]
    : configuration.selectedSkillIds.filter((value) => value !== id);
  await safe(() => configuration.updateSelection(configuration.selectedPromptId, selected));
}

async function savePrompt(): Promise<void> {
  const body = { label: promptLabel.value.trim(), content: promptContent.value.trim() };
  if (!body.label || !body.content) return;
  await safe(async () => {
    if (editingPromptId.value === null) await configuration.createPrompt(body);
    else await configuration.updatePrompt(editingPromptId.value, body);
    resetPromptForm();
  });
}

function editPrompt(id: string): void {
  const prompt = configuration.prompts.find((item) => item.id === id);
  if (prompt === undefined) return;
  editingPromptId.value = id;
  promptLabel.value = prompt.label;
  promptContent.value = prompt.content;
}

function resetPromptForm(): void {
  editingPromptId.value = null;
  promptLabel.value = "";
  promptContent.value = "";
}

async function uploadSkill(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file === undefined) return;
  if (file.name !== "SKILL.md") {
    errorMessage.value = "Skill 文件名必须严格为 SKILL.md";
    input.value = "";
    return;
  }
  const form = new FormData();
  form.append("file", file);
  await safe(() => configuration.uploadSkill(form));
  input.value = "";
}

async function safe(operation: () => Promise<void>): Promise<void> {
  errorMessage.value = null;
  try { await operation(); }
  catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : "配置操作失败";
    feedback.show("error", errorMessage.value);
  }
}
</script>

<template>
  <aside class="chat-config-sidebar" aria-label="Prompt 与 Skill 设置">
    <details open>
      <summary>Prompt</summary>
      <label>当前 Prompt
        <select :value="configuration.selectedPromptId ?? ''" @change="selectPrompt">
          <option value="">平台默认</option>
          <option v-for="prompt in configuration.prompts" :key="prompt.id" :value="prompt.id">{{ prompt.label }}</option>
        </select>
      </label>
      <form class="asset-form" @submit.prevent="savePrompt">
        <input v-model="promptLabel" aria-label="Prompt 名称" placeholder="名称" />
        <textarea v-model="promptContent" aria-label="Prompt 内容" rows="5" placeholder="Prompt 内容" />
        <div><button type="submit">{{ editingPromptId ? "保存" : "新增" }}</button><button v-if="editingPromptId" type="button" @click="resetPromptForm">取消</button></div>
      </form>
      <ul class="asset-list">
        <li v-for="prompt in configuration.prompts" :key="prompt.id">
          <span>{{ prompt.label }}</span>
          <button type="button" @click="editPrompt(prompt.id)">编辑</button>
          <button type="button" @click="safe(() => configuration.deletePrompt(prompt.id))">删除</button>
        </li>
      </ul>
    </details>
    <details open>
      <summary>Skills</summary>
      <label class="skill-upload">上传 SKILL.md<input type="file" accept=".md,text/markdown" @change="uploadSkill" /></label>
      <ul class="asset-list">
        <li v-for="skill in configuration.skills" :key="skill.id">
          <label><input type="checkbox" :checked="configuration.selectedSkillIds.includes(skill.id)" @change="toggleSkill(skill.id, $event)" />{{ skill.name }}</label>
          <small>{{ skill.description }}</small>
          <button type="button" @click="safe(() => configuration.deleteSkill(skill.id))">删除</button>
        </li>
      </ul>
    </details>
    <p v-if="errorMessage || configuration.errorMessage" class="field-error" role="alert">{{ errorMessage ?? configuration.errorMessage }}</p>
  </aside>
</template>
