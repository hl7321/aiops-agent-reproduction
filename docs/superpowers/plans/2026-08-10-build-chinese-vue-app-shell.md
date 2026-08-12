# Build Chinese Vue App Shell Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** 建立连接真实认证 API、可承载后续业务能力的中文桌面 Vue 工作台壳。

**Architecture:** Vue Router 负责 publicOnly 与 protected 路由边界，Pinia auth store 负责一次性恢复和真实认证，独立 cleanup registry 负责清除所有受保护内存 store。WorkspaceLayout 只承担导航与布局；业务页通过 RouterView 使用 edge-to-edge 画布，Chat 路由额外启用会话区域。共享状态组件与反馈 store 提供可访问、可测试的一致交互。

**Tech Stack:** Vue 3.5、Vue Router 4、Pinia 3、TypeScript 5.6 strict、Vite 6、Vitest 2、Vue Test Utils、happy-dom、Lucide Vue Next。

---

### Task 1: 固化路由和认证行为测试

**Files:**
- Create: `apps/frontend/src/router.test.ts`
- Modify: `apps/frontend/src/stores/auth.test.ts`
- Modify: `apps/frontend/src/transport/apiClient.test.ts`

**Step 1:** 写 publicOnly、protected、redirect、首次 initialize、401 清理与注册后登录测试。

**Step 2:** 运行 `npm run frontend:test`，确认新增测试因缺少实现而失败。

**Step 3:** 实现 router factory、auth initialize 去重、清理 hook 与 transport 401 hook。

**Step 4:** 重新运行测试直至通过。

### Task 2: 建立受保护数据和清理注册机制

**Files:**
- Create: `apps/frontend/src/stores/protectedStoreRegistry.ts`
- Create: `apps/frontend/src/stores/protectedStoreRegistry.test.ts`
- Create: `apps/frontend/src/stores/protectedData.ts`

**Step 1:** 写注册、注销、批量清理及内存态数据测试。

**Step 2:** 确认测试失败后，实现最小 registry 与 protectedData store。

**Step 3:** 接入 auth 的 401/登出清理路径并验证无业务 localStorage 写入。

### Task 3: 建立共享状态与反馈组件

**Files:**
- Create: `apps/frontend/src/components/states/*.vue`
- Create: `apps/frontend/src/components/feedback/AppFeedback.vue`
- Create: `apps/frontend/src/stores/feedback.ts`
- Create: `apps/frontend/src/components/components.test.ts`

**Step 1:** 写文字/ARIA、手动关闭、3 秒消失、重置 timer 与 unmount 清理测试。

**Step 2:** 确认 RED 后实现最小组件与 feedback store。

**Step 3:** 使用 fake timers 验证生命周期。

### Task 4: 实现真实认证页面与桌面 WorkspaceLayout

**Files:**
- Create: `apps/frontend/src/views/LoginView.vue`
- Create: `apps/frontend/src/views/RegisterView.vue`
- Create: `apps/frontend/src/views/ChatView.vue`
- Create: `apps/frontend/src/views/PlaceholderView.vue`
- Create: `apps/frontend/src/layouts/WorkspaceLayout.vue`
- Create: `apps/frontend/src/layouts/WorkspaceLayout.test.ts`
- Modify: `apps/frontend/src/App.vue`
- Modify: `apps/frontend/src/main.ts`

**Step 1:** 写桌面 rail、Chat 专属会话区域、账号/登出、顶栏与 placeholder 路由测试。

**Step 2:** 确认 RED 后实现页面、布局和入口接线。

**Step 3:** 验证表单调用真实 auth store 且 redirect 安全。

### Task 5: 建立设计 tokens 与桌面视觉基线

**Files:**
- Create: `apps/frontend/src/styles/tokens.css`
- Create: `apps/frontend/src/styles/global.css`
- Modify: `apps/frontend/src/main.ts`

**Step 1:** 定义专业克制的颜色、间距、边框、阴影和排版 tokens。

**Step 2:** 加入清晰 `:focus-visible`、状态文字和 `prefers-reduced-motion`。

**Step 3:** 用桌面浏览器检查登录页与认证工作台布局。

### Task 6: 完整门禁、OpenSpec 验证和归档

**Files:**
- Modify: `openspec/changes/build-chinese-vue-app-shell/tasks.md`

**Step 1:** 运行 frontend typecheck/test/build、contracts typecheck/test、相关 backend auth tests。

**Step 2:** 运行 `openspec validate --all` 与 `git diff --check`。

**Step 3:** 执行 `$openspec-verify-change`，修复发现项并重跑受影响门禁。

**Step 4:** 同步 delta specs，归档 change，并复核归档后 `openspec validate --all`。
