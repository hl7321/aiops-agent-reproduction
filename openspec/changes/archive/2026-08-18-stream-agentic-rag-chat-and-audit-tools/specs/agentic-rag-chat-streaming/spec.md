## Purpose

本能力为持久聊天会话提供由模型自主选择 tenant-safe 工具、按共享 SSE 顺序输出并在成功后保存完整回答的 Agent 流式执行合同。

## ADDED Requirements

### Requirement: 流式聊天在 owner 校验后执行 Agent
系统 SHALL 提供 `POST /chat/sessions/{sessionId}/messages:stream`，并 MUST 在保存消息或调用模型前按当前用户校验父会话。请求 SHALL 只接受 user content 与可选 metadata，客户端 MUST NOT 借此写入 assistant、system 或 tool role。

#### Scenario: 当前 owner 发起流式消息
- **WHEN** 已认证用户向自己的会话提交有效流式消息
- **THEN** 系统先验证 owner scope 并保存 user 消息，再开始 Agent 执行

#### Scenario: 跨用户发起流式消息
- **WHEN** 用户 B 向用户 A 的会话 id 提交流式消息
- **THEN** 系统返回 `AUTH_FORBIDDEN` 403，且不保存消息、不调用模型或工具

### Requirement: 模型自主选择受 tenant 约束的工具
系统 SHALL 使用 LangChain 1.x `create_agent` 让模型自主决定是否调用工具，初始工具集 MUST 至少包含 `knowledge_retrieval` 与 `get_current_time`。系统 MUST NOT 在 Agent 前无条件检索知识库；知识工具 MUST 绑定当前用户，模型提供的过滤条件只能收窄、不能扩大 owner/tenant 权限。

#### Scenario: 模型无需知识工具
- **WHEN** 模型判断当前问题无需知识检索
- **THEN** 系统生成回答且不调用 `knowledge_retrieval`、不发送虚假的工具或引用事件

#### Scenario: 模型自主检索知识
- **WHEN** 模型选择调用 `knowledge_retrieval`
- **THEN** 工具始终使用当前用户 scope，并只返回该 scope 内允许知识库的结果

#### Scenario: 模型调用当前时间工具
- **WHEN** 模型选择调用 `get_current_time`
- **THEN** 工具返回带明确时区的 ISO 8601 当前时间

### Requirement: Agent 流使用确定且真实的 SSE 事件
系统 SHALL 通过共享 SSE union 输出 `content.delta`、可选 `reasoning.delta`、`tool.call` 生命周期、`reference.source`、`complete` 或 `error`。所有事件 sequence MUST 在本轮从 1 单调增加，id MUST 稳定对应本轮与 sequence；成功流 MUST 恰好包含一次 complete。只有模型真实提供 reasoning 时才能发送 `reasoning.delta`。

#### Scenario: 最终正文包含中文和 emoji
- **WHEN** Agent 成功生成包含多字节 Unicode 字符的最终正文
- **THEN** 后端按 Unicode 字符顺序逐个发送 `content.delta`，且 tool、reasoning、reference、complete 与 error 事件不做字符拆分

#### Scenario: 模型提供真实 reasoning
- **WHEN** 模型运行事件明确携带 reasoning delta
- **THEN** 系统按原始顺序发送对应 `reasoning.delta`

#### Scenario: 模型不提供 reasoning
- **WHEN** 模型运行事件不包含 reasoning
- **THEN** 系统不合成、不推断也不发送 `reasoning.delta`

#### Scenario: 工具成功完成
- **WHEN** Agent 调用工具并成功获得结果
- **THEN** 流包含相同 toolCallId 的 started 与 completed 生命周期事件，并在知识结果存在时发送对应引用

#### Scenario: 必需分支失败
- **WHEN** 模型、工具、provider 或最终持久化失败
- **THEN** 系统发送共享安全 error，已开始工具按需发送 failed，且不发送假答案或 complete

### Requirement: 消息按完整回答边界持久化
系统 SHALL 在 Agent 开始前独立持久化 user 消息，并仅在 Agent 成功获得完整最终正文后一次性持久化 assistant 消息。assistant metadata MUST 只保存本轮 references 与 toolCallIds；失败 MUST NOT 留下部分 assistant 消息。

#### Scenario: Agent 成功完成
- **WHEN** Agent 返回完整正文且 assistant 持久化成功
- **THEN** 会话包含一条完整 assistant 消息，正文字符事件随后发送并以唯一 complete 结束

#### Scenario: Agent 中途失败
- **WHEN** user 消息已保存但 Agent 或工具失败
- **THEN** user 消息和已产生审计仍保留，但会话中不存在本轮半条 assistant 消息

#### Scenario: 客户端在完成发送前断开
- **WHEN** 完整 assistant 已持久化但客户端中断 SSE 消费
- **THEN** reload 仍可从服务端恢复完整 assistant，且系统不因断开删除消息

### Requirement: 每轮引用与历史上下文相互隔离
系统 SHALL 为每轮创建新的 references 与 toolCallIds 集合，并在 reload 时只从对应 assistant message metadata 恢复。模型历史 MAY 按配置的 context window 确定性裁剪，但 MUST 始终保留本轮 user 消息，且裁剪 MUST NOT 删除服务端历史。

#### Scenario: 连续两轮仅第一轮检索
- **WHEN** 第一轮产生知识引用而第二轮未调用知识工具
- **THEN** 第二轮 live state 与 assistant metadata 不包含第一轮引用或 toolCallIds

#### Scenario: 历史超过上下文预算
- **WHEN** 会话历史超过当前模型 capability 的上下文预算
- **THEN** 系统从最旧历史开始确定性裁剪模型输入、保留本轮 user 消息，并保持 SQLite 历史不变
