# Tasks

## 1. 侧栏结构与布局

- [x] 1.1 `ChatConfigurationSidebar` 接收 `sessions`、`selectedSessionId` 与 `onSelect`，在顶部渲染压缩摘要面板；Prompt/Skills 默认折叠，summary 显示当前 Prompt 名称
- [x] 1.2 `ChatView` 传入 `chat.sessions`、`chat.selectedDetail?.session.id` 与 `chat.selectSession`
- [x] 1.3 调整 CSS：桌面右栏 320px→280px、收紧间距、摘要列表/正文限高滚动
- [x] 1.4 增加窄屏断点：右栏堆叠到聊天区下方，验证无水平溢出

## 2. 压缩摘要组件

- [x] 2.1 新增 `ChatSummaryPanel.vue`：会话列表、已压缩/未压缩状态、选中高亮
- [x] 2.2 点击会话调用 `onSelect`，详情区展示 `memorySummary`、`compactedMessageCount`、`lastCompactedAt`、`memoryMode`
- [x] 2.3 无摘要时显示"尚未压缩"空状态；长摘要使用 `pre-wrap` + 限高滚动
- [x] 2.4 压缩完成后由 `chat.sessions` 更新驱动摘要即时刷新，不新增 API 调用

## 3. 测试

- [x] 3.1 `ChatSummaryPanel` 组件测试：列表状态、点击切换、空状态、摘要更新
- [x] 3.2 `ChatView`/侧栏测试：props 接线与当前会话高亮
- [x] 3.3 运行 `npm run frontend:test`、`npm run frontend:typecheck`、`npm run frontend:build`（137 passed）

## 4. 验证

- [ ] 4.1 桌面实机：右栏明显变窄，摘要面板默认可见，Prompt/Skills 折叠后可展开
- [ ] 4.2 用现有会话 `c0fe433c` 验证摘要展示；点击其他会话验证切换与空状态
- [ ] 4.3 窄屏（约 900px 宽）验证上下堆叠且无横向滚动
- [x] 4.4 运行 `npx --yes @fission-ai/openspec validate add-chat-summary-panel --strict`

## Workflow follow-up

- 按仓库流程同步 WIKI（`scripts/sync_wiki.py active`），并运行 `npm run docs:build`
- 实现与验证完成后，使用 `openspec-verify-change` 复核，再归档该变更
