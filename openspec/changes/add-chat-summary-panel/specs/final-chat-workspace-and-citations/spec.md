# Spec Delta

## ADDED Requirements

### Requirement: Chat 右侧栏展示压缩摘要

Chat 工作区右侧栏 SHALL 提供"压缩摘要"面板，列出当前用户的会话及其压缩状态；点击任一对话 SHALL 选中该会话并展示其 `memorySummary`、`compactedMessageCount`、`lastCompactedAt` 与 `memoryMode`。没有摘要的会话 MUST 显示明确的未压缩空状态。压缩完成后当前会话的摘要 MUST 随会话数据自动刷新。桌面端右侧栏 MUST 保持紧凑，Prompt/Skills 默认折叠；窄屏下 MUST 改为上下堆叠且不出现水平溢出。

#### Scenario: 列出会话与压缩状态

- **WHEN** 用户打开包含多个会话的 Chat 工作区
- **THEN** 右侧摘要面板列出会话标题，并标记"已压缩 N 条"或"未压缩"

#### Scenario: 点击会话查看摘要

- **WHEN** 用户点击摘要列表中的某个会话
- **THEN** 该会话被选中，右侧展示对应摘要正文、已压缩条数、最近压缩时间与记忆模式

#### Scenario: 未压缩空状态

- **WHEN** 选中的会话 `memorySummary` 为空
- **THEN** 详情区显示"尚未压缩"，而不是空白或伪造摘要

#### Scenario: 压缩后即时刷新

- **WHEN** 当前会话手动或自动完成压缩
- **THEN** 摘要面板无需刷新页面即可显示新的摘要、压缩条数与时间

#### Scenario: 窄屏布局

- **WHEN** 视口宽度不足以同时容纳聊天区与右侧栏
- **THEN** 右侧栏堆叠到聊天区下方，页面不产生水平溢出
