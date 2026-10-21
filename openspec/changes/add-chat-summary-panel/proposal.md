# 缩小聊天右侧配置栏并展示压缩摘要

## Why

聊天右侧的 Prompt/Skill 配置栏当前固定宽 320px，且两个配置区默认展开，占用了较多横向与纵向空间。

同时，压缩摘要已经由后端持久化并随会话 DTO 返回（`memorySummary`、`compactedMessageCount`、`lastCompactedAt`），但前端完全没有展示。用户在压缩后无法知道"到底压缩了什么"，只能查数据库或接口。

## What Changes

**1. 缩小右侧配置栏。**

- 桌面宽度从 320px 缩到约 280px，并收紧内边距；
- Prompt 与 Skills 默认折叠，summary 中显示当前 Prompt 名称，点击再展开；
- 窄屏下改为上下堆叠，避免横向溢出。

**2. 新增"压缩摘要"面板。**

- 面板默认展开，位于右侧栏顶部；
- 列出当前用户的会话，显示标题与压缩状态（已压缩 N 条 / 未压缩）；
- 点击某个会话即选中该会话，并在下方展示压缩摘要正文、已压缩消息数、最近压缩时间与当前记忆模式；
- 没有摘要时显示"尚未压缩"空状态；
- 手动/自动压缩完成后，当前会话的摘要应立即刷新（数据源是现有 store 的 `memorySummary`，无需新接口）。

**3. 只改前端。**

- 不新增后端接口、DTO 字段或数据库迁移；
- 不改压缩算法与摘要生成逻辑。

非目标：不允许编辑/删除摘要，不做全文搜索、导出或摘要版本历史，不改记忆窗口与压缩阈值。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `final-chat-workspace-and-citations`: 聊天右侧栏增加压缩摘要面板，并调整配置栏宽度/折叠与窄屏布局。

## Impact

| 文件 | 影响 |
|---|---|
| `apps/frontend/src/components/chat/ChatConfigurationSidebar.vue` | 收紧布局、默认折叠配置区、挂载摘要面板 |
| 新增 `apps/frontend/src/components/chat/ChatSummaryPanel.vue` | 会话列表、选中会话、摘要详情与空状态 |
| `apps/frontend/src/views/ChatView.vue` | 向侧栏传入 sessions、当前会话与选择回调 |
| `apps/frontend/src/styles/global.css` | 320px→280px、间距、摘要列表滚动与窄屏堆叠 |
| 组件/视图测试 | 摘要列表、点击切换、空状态、压缩后刷新 |

**后端/契约/数据**：无改动。
