# 会话重命名、结构化摘要与可展开摘要卡片

## Why

当前聊天会话标题只在首条用户消息时自动生成，之后无法修改；用户只能删除重建。

压缩摘要目前是一段自由文本，且只展示一句话。对"记住编号 1 到 30"这种低信息量对话，摘要确实会压成一句；但对真实排障对话，未来的模型需要更稳定地看到目标、关键标识、决定、证据和未解决事项。自由文本无法保证这些结构。

右栏摘要详情目前直接铺在列表下面，用户一旦选中会话，摘要就始终可见；这不符合"点开某条对话再看摘要"的隐私预期，也不如 AIOps 沉淀案例的就地展开卡片直观。

## What Changes

**1. 会话重命名（`rename-chat-sessions`）。**

- 新增 `PATCH /chat/sessions/{id}`，请求体 `{title}`；标题 trim 后 1..128 字符，按 owner scope 更新，并刷新 `updatedAt`。
- 左侧会话列表每项增加编辑按钮，点击进入行内输入；Enter 保存、Esc 取消。
- 不使用右键菜单：按钮在触屏、键盘和可发现性上都更简单。

**2. 结构化压缩摘要。**

- summarizer prompt 固定输出六个中文小节：
  1. **对话目标**
  2. **关键事实与标识**（服务、告警、incident/trace、时间、约束）
  3. **已做决定**
  4. **工具与证据**（工具结论、引用 ID、可信度）
  5. **未解决事项**
  6. **风险与注意事项**
- 每节用短 bullet 写；没有内容写"（无）"；不得编造。
- `memory_summary` 仍是 TEXT，不新增数据库字段；旧摘要没有标题时按单一"摘要"展示。

**3. 右栏摘要改为就地展开卡片。**

- 点击某个会话时，在该会话行下方展开一张摘要卡片（参照 AIOps 沉淀案例）；
- 同一时间只展开一张；卡片提供"收起"，再次点击同一行也可收起；
- 卡片按六个小节渲染；旧格式摘要显示为单一"摘要"节；
- 摘要不再常驻在列表底部，只有主动展开才可见。

非目标：

- 不改压缩窗口、70%/95% 阈值或自动压缩策略；
- 不提供摘要编辑、搜索、导出或版本历史；
- 不引入右键菜单；
- 不改消息存储结构。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `chat-session-management`: 新增显式会话重命名与标题校验。
- `api-and-sse-contracts`: 登记 `PATCH /chat/sessions/{id}` 与标题更新请求。
- `chat-session-memory-modes`: 压缩摘要采用固定六段结构，并兼容旧摘要。
- `final-chat-workspace-and-citations`: 左侧行内重命名；右侧摘要按会话就地展开卡片。

## Impact

**后端**

| 文件 | 影响 |
|---|---|
| `chat/router.py` | 新增 PATCH 路由 |
| `chat/service.py` / `chat/repositories.py` | 标题更新、owner scope、updatedAt |
| `chat/memory/summarizer.py` | 六段式摘要 prompt |
| `chat/memory/service.py` | 旧摘要兼容/结构归一化 |
| `api_contracts.py` + `packages/api-contracts` | 新请求/响应与 OpenAPI |

**前端**

| 文件 | 影响 |
|---|---|
| `ChatSessionSidebar.vue` | 编辑按钮 + 行内输入 |
| `chatClient.ts` / `stores/chat.ts` | `renameSession` |
| `ChatSummaryPanel.vue` | 就地展开卡片、六节渲染、收起 |
| 组件测试 | 重命名、摘要切换、旧格式兼容 |

**数据**：`chat_sessions.title` 已是 VARCHAR(128)，`memory_summary` 已是 TEXT；无迁移。
