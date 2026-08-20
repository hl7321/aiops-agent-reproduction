# Final Chat Workspace and Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 P14–P18 的真实 Chat API/SSE、Prompt/Skill、memory、MCP 与 retrieval citation 组合成最终桌面 `/chat` 工作区。

**Architecture:** WorkspaceLayout 唯一拥有会话栏，ChatView 组合 transcript/composer/右侧配置；Chat store 串行消费 SSE 并在 complete 后服务端对账。共享 citation 合同贯穿 retrieval、SSE、assistant metadata 和 UI，安全 Markdown 与引用/工具组件保持独立可测。

**Tech Stack:** Vue 3.5、Pinia 3、Vue Router 4、TypeScript 5.6 strict、Vitest 2、marked、DOMPurify、Lucide、FastAPI/Pydantic v2、共享 SSE contracts。

**Spec:** `openspec/changes/build-final-chat-workspace-and-citations/design.md`

## Global Constraints

- 所有产品数据来自真实 API/SSE，不写 localStorage、不使用静态领域数组。
- `content.delta` 在 `for await` 循环内每字符更新后等待约 28 ms，不使用 requestAnimationFrame 或独立队列。
- Markdown 必须经 marked + DOMPurify，禁止不可信 raw HTML。
- 当前验收只面向桌面 Web；不新增移动专用替代流程。
- 所有 OpenSpec artifacts 使用简体中文；完成后运行完整门禁并同步归档。

---

### Task 1: 统一完整 Citation 合同

**Files:**
- Modify: `packages/api-contracts/src/chat.ts`
- Modify: `packages/api-contracts/src/sse.ts`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Modify: `apps/backend/src/super_ai/chat/agent_events.py`
- Test: `packages/api-contracts/src/chat.test.ts`
- Test: `apps/backend/tests/chat/test_agent_events.py`

**Interfaces:**
- Consumes: `KnowledgeRetrievalCitation`。
- Produces: `ChatReference` 与 `ReferenceSourceEvent.data.source` 的同形完整 citation。

- [ ] **Step 1: 写合同失败测试**

```ts
const citation: ChatReference = {
  chunkId: "c1", documentId: "d1", knowledgeBaseId: "kb1",
  source: "runbook.md", excerpt: "证据", metadata: {},
  vectorRank: null, vectorScore: null, bm25Rank: 1, bm25Score: 2,
  rrfScore: 1 / 61, rerankRank: 1, rerankScore: 0.9, score: 0.9,
};
expect(isSseEvent(referenceEvent(citation))).toBe(true);
expect(isSseEvent(referenceEvent({ id: "c1", title: "old" }))).toBe(false);
```

- [ ] **Step 2: 运行测试确认因旧 id/title 形状失败**

Run: `npm run contracts:test -- --run src/chat.test.ts src/index.test.ts`
Expected: FAIL，完整 citation 不能赋给旧 `ReferenceSource`。

- [ ] **Step 3: 最小实现共享形状与后端映射**

```ts
export type ChatReference = KnowledgeRetrievalCitation;
export interface ReferenceSourceEvent extends SseEventBase<"reference.source"> {
  data: { source: ChatReference };
}
```

```python
class ChatReference(KnowledgeRetrievalCitation):
    @model_validator(mode="after")
    def score_matches_rerank(self) -> "ChatReference":
        if self.score != self.rerank_score:
            raise ValueError("score 必须等于 rerankScore")
        return self
```

- [ ] **Step 4: 运行 contracts 与 backend 定向测试**

Run: `npm run contracts:typecheck && npm run contracts:test && cd apps/backend && uv run pytest tests/chat/test_agent_events.py tests/chat/test_agent_runner.py`
Expected: PASS。

### Task 2: 串行流状态与 28 ms 背压

**Files:**
- Modify: `apps/frontend/src/stores/chat.ts`
- Modify: `apps/frontend/src/stores/chat.test.ts`

**Interfaces:**
- Consumes: `ChatClient.streamMessage(): AsyncIterable<SseEvent>`。
- Produces: `toolAudits`、live 状态、`sleep(milliseconds)` 注入与 complete 对账。

- [ ] **Step 1: 写受控 iterator/fake timer 失败测试**

```ts
vi.useFakeTimers();
const pending = store.streamMessage({ content: "测试" });
await nextTick();
expect(store.liveContent).toBe("你");
await vi.advanceTimersByTimeAsync(27);
expect(store.liveContent).toBe("你");
await vi.advanceTimersByTimeAsync(1);
expect(store.liveContent).toBe("你好");
await pending;
expect(client.getSession).toHaveBeenCalledOnce();
```

- [ ] **Step 2: 运行测试确认旧 store 无延迟且不对账 audits**

Run: `npm run frontend:test -- --run src/stores/chat.test.ts`
Expected: FAIL。

- [ ] **Step 3: 在 for-await 内实现唯一节奏点**

```ts
if (event.type === "content.delta") {
  liveContent.value += event.data.delta;
  await dependencies.sleep(28);
}
```

- [ ] **Step 4: 运行 store 测试确认顺序、隔离、401 与缺 complete**

Run: `npm run frontend:test -- --run src/stores/chat.test.ts`
Expected: PASS。

### Task 3: 安全 Markdown、引用与工具组件

**Files:**
- Create: `apps/frontend/src/chat/renderSafeMarkdown.ts`
- Create: `apps/frontend/src/chat/ChatMessageBubble.vue`
- Create: `apps/frontend/src/chat/ChatCitationList.vue`
- Create: `apps/frontend/src/chat/ChatToolActivity.vue`
- Test: corresponding `*.test.ts`

**Interfaces:**
- Consumes: `ChatMessage`、完整 `ChatReference`、`ToolCallEvent.data`、`AgentToolCallAudit`。
- Produces: 已清洗 HTML、最多五条 citation、默认折叠安全工具摘要。

- [ ] **Step 1: 写恶意 Markdown 和 citation 字面 fixture 测试**

```ts
expect(renderSafeMarkdown('<img src=x onerror="boom"><script>boom</script>')).not.toContain("onerror");
expect(wrapper.findAll("[data-citation]")).toHaveLength(5);
expect(wrapper.text()).toContain("未命中");
expect(wrapper.text()).not.toContain('{"secret"');
```

- [ ] **Step 2: 运行测试确认组件/函数不存在**

Run: `npm run frontend:test -- --run src/chat`
Expected: FAIL with missing module/component。

- [ ] **Step 3: 实现纯渲染边界和专责组件**

```ts
export function renderSafeMarkdown(source: string): string {
  const rendered = marked.parse(source, { async: false });
  return DOMPurify.sanitize(rendered, { FORBID_TAGS: ["script", "iframe", "style"] });
}
```

- [ ] **Step 4: 运行组件测试与 typecheck**

Run: `npm run frontend:typecheck && npm run frontend:test -- --run src/chat`
Expected: PASS。

### Task 4: Workspace 会话栏与 Chat 组合布局

**Files:**
- Create: `apps/frontend/src/chat/ChatSessionSidebar.vue`
- Create: `apps/frontend/src/chat/ChatComposer.vue`
- Create: `apps/frontend/src/chat/ChatMemoryControls.vue`
- Create: `apps/frontend/src/chat/ChatConfigurationSidebar.vue`
- Modify: `apps/frontend/src/layouts/WorkspaceLayout.vue`
- Modify: `apps/frontend/src/views/ChatView.vue`
- Modify: `apps/frontend/src/styles/global.css`
- Test: `WorkspaceLayout.test.ts`、`ChatView.test.ts` 与组件测试。

**Interfaces:**
- Consumes: `useChatStore`、`useChatConfigurationStore`、feedback store。
- Produces: 唯一会话栏、conversation-first transcript、固定 composer 和右侧配置。

- [ ] **Step 1: 写 IME/键盘与布局失败测试**

```ts
await textarea.trigger("keydown", { key: "Enter", isComposing: true });
expect(streamMessage).not.toHaveBeenCalled();
await textarea.trigger("keydown", { key: "Enter", shiftKey: true });
expect(streamMessage).not.toHaveBeenCalled();
expect(wrapper.find(".chat-transcript--empty").text()).toBe("");
expect(wrapper.findAll('[aria-label="会话区域"]')).toHaveLength(1);
```

- [ ] **Step 2: 运行测试确认占位页面失败**

Run: `npm run frontend:test -- --run src/layouts/WorkspaceLayout.test.ts src/views/ChatView.test.ts`
Expected: FAIL。

- [ ] **Step 3: 实现组件组合与 CSS minmax/overflow/resize 边界**

```css
.chat-workspace { height: 100%; display: grid; grid-template-columns: minmax(0, 1fr) 320px; overflow: hidden; }
.chat-transcript { min-height: 0; overflow: auto; }
.chat-composer textarea { resize: none; }
```

- [ ] **Step 4: 运行前端全测试**

Run: `npm run frontend:typecheck && npm run frontend:test && npm run frontend:build`
Expected: PASS。

### Task 5: 验证、真实 smoke 记录与 OpenSpec 生命周期

**Files:**
- Create: `docs/runbooks/final-chat-workspace-smoke.md`
- Modify: `apps/frontend/README.md`
- Modify: OpenSpec tasks/specs during verification and sync。

**Interfaces:**
- Consumes: 所有 P19 工程产物。
- Produces: 可复验门禁证据、真实 smoke 结论、同步主规格与归档 change。

- [ ] **Step 1: 运行完整工程门禁**

```bash
npm run contracts:typecheck
npm run contracts:test
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
npm run frontend:test:secret
cd apps/backend && uv run ruff check . && uv run pyright && uv run pytest
cd ../.. && openspec validate --all && git diff --check
```

- [ ] **Step 2: 有真实服务时执行普通问答与知识/MCP 自主工具桌面 smoke**

Expected: 可用时记录实际结果；不可用时记录未执行原因，不把 fake transport 当真实连通。

- [ ] **Step 3: 执行 verify、修复、同步与 archive**

Run: `openspec status --change build-final-chat-workspace-and-citations --json`
Expected: artifacts complete、tasks complete、verify 无 CRITICAL/WARNING、主规格匹配 delta、change 移入日期归档目录。
