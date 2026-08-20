# Knowledge Base Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `/knowledge` 建立连接真实后端的中文桌面知识库工作区，完成文档上传、持久索引跟踪、切分预览、覆盖、重试、重建与删除闭环。

**Architecture:** 扩展现有 `knowledgeClient` 作为 typed transport facade；单一 Pinia store 保存服务端 DTO、界面选择和短生命周期请求状态，并通过 background-job 列表恢复文档 index task 关联。Vue 组件拆分上传、文档表与行内详情，所有领域操作经 store action，列表和详情各自维持有界滚动。

**Tech Stack:** Vue 3.5、Pinia 3、Vue Router 4、TypeScript 5.6 strict、Vitest 2、Vue Test Utils、共享 API contracts、FastAPI 后端。

## Global Constraints

- `/knowledge` 只连接真实受保护 API；不得用 localStorage、静态数组或假任务保存领域数据。
- 上传 policy 只允许 `.md`/`.pdf`、最大 10 MiB；前端提示不替代后端权威校验。
- `fixed-character` 才发送 `maxCharacters`/`overlap`，且 `overlap < maxCharacters`；其他策略只发送 `strategy`。
- 活动任务约每 2 秒 poll；取消继续属于通用 background-job 能力。
- 401/logout 必须清空 knowledge store 和 timer，不调用领域删除 API。
- 验收只面向桌面浏览器，不新增移动专用导航或替代流程。

---

### Task 1: Typed Knowledge Client

**Files:**
- Modify: `apps/frontend/src/knowledge/knowledgeClient.ts`
- Modify: `apps/frontend/src/knowledge/knowledgeClient.test.ts`

**Interfaces:**
- Produces: `listKnowledgeBases()`, `listDocuments(kb)`, `getDocument(kb, document)`, `getChunkPreview(kb, document)`, `deleteDocument(kb, document)`, `listBackgroundJobs()`。
- Retains: upload/create/get/retry index-task 方法与 `ApiResult<T>` envelope。

- [ ] 编写按字面 path、method、multipart body 和共享 DTO 断言的失败测试。
- [ ] 运行 `npm run test --workspace @super-ai/frontend -- src/knowledge/knowledgeClient.test.ts`，确认因方法缺失而 RED。
- [ ] 最小扩展 typed client 并保持所有请求委托 `ApiClient`。
- [ ] 重新运行 targeted test，确认 GREEN。

### Task 2: Pinia Knowledge Store

**Files:**
- Create: `apps/frontend/src/stores/knowledge.ts`
- Create: `apps/frontend/src/stores/knowledge.test.ts`
- Modify: `apps/frontend/src/stores/protectedStoreRegistry.ts` only if existing registration interface needs a typed extension.

**Interfaces:**
- Produces: `useKnowledgeStore` with server DTO state, `initialize`, `upload`, `confirmOverwrite`, `loadPreview`, `retryTask`, `rebuildDocument`, `requestDelete`, `confirmDelete`, `reset`。
- Uses one timer and generation token; recovers latest task per document from validated `BackgroundJob` payload and resource id.

- [ ] 编写初始化、服务端列表、单 KB 选择、注册清理和无 localStorage 行为的失败测试并确认 RED。
- [ ] 实现最小 store 初始化和 reset，运行 GREEN。
- [ ] 编写上传字段、冲突覆盖、删除刷新、任务创建与错误恢复的失败测试并确认 RED。
- [ ] 实现上传草稿、确认动作及服务端刷新，运行 GREEN。
- [ ] 编写 fake timer 测试覆盖约 2 秒 poll、终态停止、retry、重建、恢复关联与迟到响应，确认 RED。
- [ ] 实现单调度器与任务 actions，运行 targeted suite GREEN。

### Task 3: Desktop Knowledge Components and Route

**Files:**
- Create: `apps/frontend/src/views/KnowledgeView.vue`
- Create: `apps/frontend/src/knowledge/KnowledgeUploadPanel.vue`
- Create: `apps/frontend/src/knowledge/KnowledgeDocumentTable.vue`
- Create: `apps/frontend/src/knowledge/KnowledgeDocumentDetail.vue`
- Create: `apps/frontend/src/views/KnowledgeView.test.ts`
- Modify: `apps/frontend/src/router.ts`
- Modify: `apps/frontend/src/router.test.ts`

**Interfaces:**
- View initializes/resets polling lifecycle; child components call store actions without duplicating DTO state.
- Upload emits valid `File` plus `ChunkingConfig`; detail loads preview from the selected document endpoint.

- [ ] 编写真实 `/knowledge` 路由、单 KB selector 隐藏、accept policy、策略字段和中文状态的失败组件测试，确认 RED。
- [ ] 实现 view/upload/table 最小交互，运行 GREEN。
- [ ] 编写默认折叠行内详情、preview、确认、ARIA 和滚动 CSS 约束测试，确认 RED。
- [ ] 实现 detail、状态徽标、dialog 与 `min-height:0`/overflow/max-height CSS，运行 GREEN。

### Task 4: Gates, Browser Smoke and OpenSpec Lifecycle

**Files:**
- Modify: `openspec/changes/build-knowledge-base-workspace/tasks.md`
- Create: `docs/runbooks/knowledge-base-workspace-smoke.md`
- Sync: `openspec/specs/knowledge-base-workspace/spec.md`
- Modify on sync: `openspec/specs/chinese-vue-app-shell/spec.md`

**Interfaces:**
- Browser smoke uses local FastAPI/Vite and an authenticated real user; MD/PDF flows use actual endpoints and persistent SQLite records.

- [ ] 运行 frontend typecheck/test/build、contracts typecheck/test、相关 backend tests、`openspec validate --all` 和 `git diff --check`。
- [ ] 启动本机服务并在桌面浏览器完成 MD/PDF 上传、显式索引、真实 preview 与删除，记录 Qwen/Milvus 实际状态。
- [ ] 按 `openspec-verify-change` 将每项 requirement/scenario 映射到代码与测试，修复全部 CRITICAL/WARNING。
- [ ] 同步两份 delta spec、重新验证并归档 change，确认活动 change 列表为空。
