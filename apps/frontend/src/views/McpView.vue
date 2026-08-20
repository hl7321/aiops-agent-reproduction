<script setup lang="ts">
import { Cable, CircleCheck, Plus, RefreshCw, Server, Trash2 } from "lucide-vue-next";
import { onBeforeUnmount, onMounted, reactive } from "vue";

import type { CreateMcpConnectionRequest, McpConnection } from "@super-ai/api-contracts";

import AppEmptyState from "../components/states/AppEmptyState.vue";
import AppErrorState from "../components/states/AppErrorState.vue";
import AppLoadingState from "../components/states/AppLoadingState.vue";
import AsyncStatusBadge from "../components/states/AsyncStatusBadge.vue";
import { useFeedbackStore } from "../stores/feedback";
import { useMcpStore } from "../stores/mcp";

const store = useMcpStore();
const feedback = useFeedbackStore();
const draft = reactive<CreateMcpConnectionRequest>({
  name: "", transport: "streamable_http", url: "", enabled: true,
  timeoutSeconds: 30, retries: 1,
});

onMounted(async () => {
  try { await store.initialize(); } catch { /* store 已提供安全错误 */ }
});
onBeforeUnmount(() => store.reset());

function resetDraft(): void {
  Object.assign(draft, {
    name: "", transport: "streamable_http", url: "", enabled: true,
    timeoutSeconds: 30, retries: 1,
  });
  store.editingId = null;
}

function edit(connection: McpConnection): void {
  store.editingId = connection.id;
  Object.assign(draft, {
    name: connection.name, transport: connection.transport, url: connection.url,
    enabled: connection.enabled, timeoutSeconds: connection.timeoutSeconds,
    retries: connection.retries,
  });
}

async function save(): Promise<void> {
  try {
    const body = { ...draft };
    if (store.editingId === null) await store.create(body);
    else await store.update(store.editingId, body);
    feedback.show("success", "MCP 连接已保存");
    resetDraft();
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "MCP 连接保存失败");
  }
}

async function check(id: string): Promise<void> {
  try {
    await store.check(id);
    const result = store.checkById[id];
    feedback.show(result?.status === "connected" ? "success" : "error", result?.status === "connected" ? "真实 MCP 检查成功" : (result?.error ?? "真实 MCP 检查失败"));
  } catch (error: unknown) {
    feedback.show("error", error instanceof Error ? error.message : "真实 MCP 检查失败");
  }
}

async function toggle(connection: McpConnection): Promise<void> {
  try { await store.toggleEnabled(connection.id, !connection.enabled); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "启停失败"); }
}

async function confirmDelete(): Promise<void> {
  try { await store.confirmDelete(); feedback.show("success", "MCP 连接已删除"); }
  catch (error: unknown) { feedback.show("error", error instanceof Error ? error.message : "删除失败"); }
}
</script>

<template>
  <div class="mcp-workspace" data-route-canvas="mcp">
    <header class="mcp-heading">
      <div class="mcp-heading__icon"><Cable :size="22" aria-hidden="true" /></div>
      <div><p class="eyebrow">MCP</p><h2>MCP Servers</h2><p>管理当前账号真实可访问的 MCP Server，并实时发现工具。</p></div>
    </header>

    <aside class="mcp-warning" role="note">
      完整 URL 会由服务器保存并返回；当前不支持自定义 headers。禁止将 token、secret 或 password 放入 URL query。
    </aside>

    <section class="mcp-grid">
      <form class="mcp-form" aria-label="MCP 连接编辑表单" @submit.prevent="save">
        <div class="mcp-form__title"><Server :size="18" aria-hidden="true" /><strong>{{ store.editingId ? "编辑连接" : "新建连接" }}</strong></div>
        <label>名称<input v-model.trim="draft.name" required maxlength="120" /></label>
        <label>Transport<select v-model="draft.transport"><option value="streamable_http">Streamable HTTP</option><option value="sse">SSE</option></select></label>
        <label>URL<input v-model.trim="draft.url" required type="url" placeholder="https://host.example/mcp" /></label>
        <div class="mcp-form__row"><label>超时（秒）<input v-model.number="draft.timeoutSeconds" required type="number" min="1" max="300" /></label><label>发现重试次数<input v-model.number="draft.retries" required type="number" min="0" max="5" /></label></div>
        <label class="mcp-checkbox"><input v-model="draft.enabled" type="checkbox" />启用此连接</label>
        <div class="mcp-form__actions"><button v-if="store.editingId" type="button" @click="resetDraft">取消</button><button class="button button--primary" type="submit" :disabled="store.saving"><Plus :size="16" aria-hidden="true" />{{ store.saving ? "保存中" : "保存连接" }}</button></div>
      </form>

      <div class="mcp-panel">
        <AppLoadingState v-if="store.loading" message="正在读取 MCP 连接" />
        <AppErrorState v-else-if="store.errorMessage" :message="store.errorMessage" />
        <AppEmptyState v-else-if="store.connections.length === 0" title="暂无 MCP 连接" description="添加真实 MCP Server 后可执行连接检查与工具发现。" />
        <div v-else class="mcp-connection-list" aria-label="MCP 连接列表">
          <article v-for="connection in store.connections" :key="connection.id" class="mcp-card">
            <header><div><strong>{{ connection.name }}</strong><span>{{ connection.transport === "sse" ? "SSE" : "Streamable HTTP" }}</span></div><AsyncStatusBadge :status="connection.enabled ? 'success' : 'idle'" :label="connection.enabled ? '已启用' : '已停用'" /></header>
            <p class="mcp-url">{{ connection.url }}</p>
            <p class="mcp-check"><CircleCheck :size="15" aria-hidden="true" />最近检查：{{ connection.lastCheck ?? "尚未检查" }}<span v-if="connection.lastError">；{{ connection.lastError }}</span></p>
            <div class="mcp-tools" aria-label="真实发现工具">
              <strong>发现工具（{{ connection.discoveredTools.length }}）</strong>
              <p v-if="connection.discoveredTools.length === 0">尚无真实工具快照</p>
              <ul v-else><li v-for="item in connection.discoveredTools" :key="item.name"><code>{{ item.name }}</code><span>{{ item.description ?? "无描述" }}</span></li></ul>
            </div>
            <footer><button type="button" @click="toggle(connection)">{{ connection.enabled ? "停用" : "启用" }}</button><button type="button" @click="edit(connection)">编辑</button><button type="button" @click="check(connection.id)"><RefreshCw :size="15" aria-hidden="true" />真实检查</button><button type="button" aria-label="删除连接" @click="store.requestDelete(connection.id)"><Trash2 :size="15" aria-hidden="true" />删除</button></footer>
          </article>
        </div>
      </div>
    </section>

    <section v-if="store.deleteConfirmation" class="mcp-dialog" role="dialog" aria-modal="true" aria-label="确认删除 MCP 连接"><strong>确认删除 {{ store.deleteConfirmation.name }}？</strong><p>只删除当前账号保存的连接，不会修改外部 MCP Server。</p><div><button type="button" @click="store.cancelDelete">取消</button><button class="button button--primary" type="button" @click="confirmDelete">确认删除</button></div></section>
  </div>
</template>

<style scoped>
.mcp-workspace { height: calc(100vh - 74px); min-width: 0; min-height: 0; display: grid; grid-template-rows: auto auto minmax(0, 1fr); gap: var(--space-4); padding: var(--space-5); overflow: hidden; }
.mcp-heading { display: flex; align-items: center; gap: var(--space-3); }.mcp-heading__icon { width: 44px; height: 44px; display: grid; place-items: center; border: 1px solid #cfe0db; border-radius: 12px; color: var(--color-accent); background: var(--color-accent-soft); }.mcp-heading h2 { margin: 3px 0; font-size: 23px; }.mcp-heading p:last-child { margin: 0; color: var(--color-text-muted); font-size: 12px; }
.mcp-warning { border: 1px solid #dfd4af; border-radius: var(--radius-sm); padding: 10px 14px; color: #6a5721; background: #fffaf0; font-size: 12px; }
.mcp-grid { min-height: 0; display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr); gap: var(--space-4); }.mcp-form,.mcp-panel { min-height: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); }.mcp-form { align-content: start; display: grid; gap: var(--space-3); padding: var(--space-4); overflow: auto; }.mcp-form__title { display: flex; gap: 8px; align-items: center; }.mcp-form label { display: grid; gap: 6px; font-size: 12px; color: var(--color-text-muted); }.mcp-form input,.mcp-form select { min-width: 0; height: 39px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0 10px; background: white; }.mcp-form__row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }.mcp-form .mcp-checkbox { display: flex; align-items: center; }.mcp-checkbox input { width: 16px; height: 16px; }.mcp-form__actions { display: flex; justify-content: flex-end; gap: 8px; }.mcp-form__actions button,.mcp-card footer button { min-height: 36px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); display: inline-flex; align-items: center; gap: 5px; padding: 0 11px; background: white; cursor: pointer; }
.mcp-panel { overflow: hidden; }.mcp-connection-list { height: 100%; min-height: 0; display: grid; align-content: start; gap: var(--space-3); padding: var(--space-4); overflow: auto; }.mcp-card { min-width: 0; border: 1px solid var(--color-border); border-radius: var(--radius-sm); display: grid; gap: 10px; padding: var(--space-4); }.mcp-card header,.mcp-card footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.mcp-card header > div { display: grid; gap: 3px; }.mcp-card header span,.mcp-check { color: var(--color-text-muted); font-size: 11px; }.mcp-url { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: ui-monospace, monospace; font-size: 12px; }.mcp-check { margin: 0; display: flex; align-items: center; gap: 5px; }.mcp-tools { max-height: 150px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 10px; overflow: auto; }.mcp-tools ul { margin: 8px 0 0; display: grid; gap: 6px; padding: 0; list-style: none; }.mcp-tools li { display: grid; grid-template-columns: minmax(120px, .4fr) 1fr; gap: 10px; }.mcp-tools span,.mcp-tools p { color: var(--color-text-muted); font-size: 11px; }.mcp-card footer { justify-content: flex-end; flex-wrap: wrap; }
.mcp-dialog { position: fixed; inset: 0; z-index: 30; width: min(440px, calc(100vw - 48px)); height: fit-content; margin: auto; border: 1px solid var(--color-border); border-radius: var(--radius-md); display: grid; gap: var(--space-3); padding: var(--space-5); background: var(--color-surface); box-shadow: 0 0 0 100vmax rgb(23 32 38 / 35%), var(--shadow-panel); }.mcp-dialog p { margin: 0; color: var(--color-text-muted); }.mcp-dialog div { display: flex; justify-content: flex-end; gap: 8px; }
</style>
