<script setup lang="ts">
import type { AgentToolCallAudit, ToolCallEvent } from "@super-ai/api-contracts";

defineProps<{
  reasoning: string;
  liveToolCalls: Readonly<Record<string, ToolCallEvent["data"]>>;
  audits: readonly AgentToolCallAudit[];
}>();
</script>

<template>
  <div v-if="reasoning || Object.keys(liveToolCalls).length || audits.length" class="chat-activity">
    <details v-if="reasoning">
      <summary>模型推理（模型真实返回）</summary>
      <p>{{ reasoning }}</p>
    </details>
    <details v-if="Object.keys(liveToolCalls).length || audits.length">
      <summary>工具调用</summary>
      <ul class="tool-activity-list">
        <li v-for="tool in liveToolCalls" :key="tool.toolCallId">
          <strong>{{ tool.toolName }}</strong><span>{{ tool.lifecycle }}</span>
          <p v-if="tool.error">{{ tool.error.message }}</p>
        </li>
        <li v-for="audit in audits" :key="audit.id">
          <strong>{{ audit.toolName }}</strong><span>{{ audit.status }}</span>
          <p v-if="audit.resultSummary">{{ audit.resultSummary }}</p>
          <p v-else-if="audit.errorMessage">{{ audit.errorMessage }}</p>
        </li>
      </ul>
    </details>
  </div>
</template>
