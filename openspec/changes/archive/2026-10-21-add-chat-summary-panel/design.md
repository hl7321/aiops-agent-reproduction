# Design

## Context

见 `proposal.md - Why`。现有 ChatSession DTO 已包含 `memorySummary`、`compactedMessageCount`、`lastCompactedAt` 与 `memoryMode`，`chat.sessions` 也由 store 维护，因此无需后端改动。

## Goals / Non-Goals

**Goals：**

- 右栏更窄、更紧凑，Prompt/Skill 默认折叠；
- 用户可浏览各会话的压缩摘要；
- 压缩完成后当前摘要即时可见。

**Non-Goals：**

- 不改摘要生成、压缩阈值或记忆窗口；
- 不新增 API/DTO/数据库字段；
- 不做摘要编辑、搜索或版本历史。

## Decisions

### 1. 摘要面板作为右栏顶部独立组件

新增 `ChatSummaryPanel.vue`，接收：

- `sessions: ChatSession[]`
- `selectedSessionId: string | null`
- `onSelect: (id: string) => Promise<void>`

组件只负责展示与触发选择，不直接调用 API。`ChatView` 把 `chat.sessions`、`chat.selectedDetail?.session.id` 和 `chat.selectSession` 传给 `ChatConfigurationSidebar`，由侧栏渲染摘要面板与配置区。

备选：在面板内直接访问 Pinia store。会降低可测试性，并让组件耦合全局状态，不采用。

### 2. 摘要列表与详情

- 列表展示所有会话，按更新时间倒序（沿用 store 顺序）；
- 每项显示标题与状态：`已压缩 N 条` 或 `未压缩`；
- 点击项调用 `onSelect(id)`，选中项高亮；
- 详情区展示选中会话的 `memorySummary`、`compactedMessageCount`、`lastCompactedAt`、`memoryMode`；
- 摘要为空时显示中文空状态"尚未压缩"。

### 3. 空间控制

- 右栏宽度 320px → 280px，内边距收紧；
- Prompt/Skills 的 `<details>` 默认关闭，summary 显示当前 Prompt 名称；
- 摘要列表与正文分别设置最大高度并滚动，避免撑开整栏；
- `@media (max-width: 980px)` 下右栏改为堆叠到聊天区下方，避免水平溢出。

### 4. 数据刷新

摘要数据来自 `chat.sessions`。现有 `applyDetail` 在压缩后会同时更新选中详情与会话列表，因此组件随 props 自动刷新；不额外轮询。

## Risks / Trade-offs

- **会话很多时列表很长** → 设置最大高度与滚动，并保持列表顺序稳定。
- **摘要正文很长** → `white-space: pre-wrap` + 最大高度滚动。
- **折叠 Prompt 后看不到当前选择** → summary 文案显示当前 Prompt 名称。
- **窄屏堆叠改变布局** → 在 980px 断点以下只改变列布局，不隐藏功能。

## Migration Plan

无数据库、配置或 API 迁移；回滚只需恢复前端组件与 CSS。

## Open Questions

（无）
