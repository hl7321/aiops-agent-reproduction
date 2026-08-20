# Agentic RAG Chat 流式执行规格

## Purpose

本能力为持久聊天会话提供由模型自主选择 tenant-safe 工具、按共享 SSE 顺序输出并在成功后保存完整回答的 Agent 流式执行合同。

## Requirements

### Requirement: 流式聊天在 owner 校验后执行 Agent
系统 SHALL 提供 `POST /chat/sessions/{sessionId}/messages:stream`，并 MUST 在保存消息或调用模型前按当前用户校验父会话。请求 SHALL 只接受 user content 与可选 metadata，客户端 MUST NOT 借此写入 assistant、system 或 tool role。

#### Scenario: 当前 owner 发起流式消息
- **WHEN** 已认证用户向自己的会话提交有效流式消息
- **THEN** 系统先验证 owner scope 并保存 user 消息，再开始 Agent 执行

#### Scenario: 跨用户发起流式消息
- **WHEN** 用户 B 向用户 A 的会话 id 提交流式消息
- **THEN** 系统返回 `AUTH_FORBIDDEN` 403，且不保存消息、不调用模型或工具

### Requirement: 模型自主选择受 tenant 约束的工具
系统 SHALL 使用 LangChain 1.x `create_agent` 让模型自主决定是否调用工具，初始工具集 MUST 至少包含 `knowledge_retrieval`、`get_current_time` 与当前请求 owner-scoped 的 `load_skill`。系统 MUST NOT 在 Agent 前无条件检索知识库或加载 Skill 正文；知识工具 MUST 绑定当前用户，模型提供的过滤条件只能收窄、不能扩大 owner/tenant 权限；`load_skill` MUST 只能读取本轮选中的当前 owner Skill。每轮 system prompt MUST 先保留不可覆盖的平台安全规则，再装配当前用户 Prompt 与仅含 name/description 的选中 Skill catalog。reasoning 仍只能来自模型真实事件。

#### Scenario: 模型无需知识工具
- **WHEN** 模型判断当前问题无需知识检索
- **THEN** 系统生成回答且不调用 `knowledge_retrieval`、不发送虚假的工具或引用事件

#### Scenario: 模型自主检索知识
- **WHEN** 模型选择调用 `knowledge_retrieval`
- **THEN** 工具始终使用当前用户 scope，并只返回该 scope 内允许知识库的结果

#### Scenario: 模型调用当前时间工具
- **WHEN** 模型选择调用 `get_current_time`
- **THEN** 工具返回带明确时区的 ISO 8601 当前时间

#### Scenario: 模型按需调用 Skill
- **WHEN** 模型根据摘要判断需要本轮已选 Skill
- **THEN** 模型调用 `load_skill` 后才取得正文，工具仍强制当前 owner 与选择白名单

#### Scenario: 用户配置不能覆盖平台边界
- **WHEN** 当前用户 Prompt 或 Skill 正文要求跨 tenant 访问或替换可信工具规则
- **THEN** Agent 的 CurrentUser、Repository scope 与工具实现保持不变，越权内容不能生效

#### Scenario: reasoning 保持真实来源
- **WHEN** 动态 Prompt/Skill 装配完成且模型未提供 reasoning event
- **THEN** 系统不合成、不推断也不发送 reasoning

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
系统 SHALL 为每轮创建新的 references 与 toolCallIds 集合，并在 reload 时只从对应 assistant message metadata 恢复。模型历史 MUST 由当前会话的可用摘要与压缩高水位之后的消息装配，MUST NOT 删除、改写服务端完整历史或回退为无摘要的最旧消息裁剪；当前候选 user 消息 MUST 只在 95% 安全检查通过后保存并进入本轮模型输入。

#### Scenario: 连续两轮仅第一轮检索
- **WHEN** 第一轮产生知识引用而第二轮未调用知识工具
- **THEN** 第二轮 live state 与 assistant metadata 不包含第一轮引用或 toolCallIds

#### Scenario: 历史超过上下文预算
- **WHEN** 会话存在历史摘要与压缩消息高水位
- **THEN** 模型输入包含该会话摘要和高水位之后的消息，不重复发送已摘要逐条历史，SQLite 完整历史保持不变

#### Scenario: 候选轮次达到硬上限
- **WHEN** 当前模式完成允许的自动压缩后，包含候选 user 消息的预算达到模型窗口 95%
- **THEN** 系统返回共享上下文上限错误，且不保存候选 user 消息、不调用模型或工具

### Requirement: 流式错误复用上下文上限目录
流式聊天 SHALL 对 `CHAT_CONTEXT_LIMIT_REACHED` 使用与 HTTP failure envelope 相同的错误定义。响应尚未开始时 MUST 返回 HTTP 409；响应已经开始时 MUST 发送共享 SSE `error` 形状，且两者不能具有冲突的 category、status 或默认消息。

#### Scenario: 流开始前预算拒绝
- **WHEN** 候选预算在创建 StreamingResponse 前达到 95%
- **THEN** 客户端收到 409 failure envelope 而不是伪装成成功的空 SSE 流

### Requirement: Chat Agent 按请求装配真实 MCP tools
每轮 Chat Agent SHALL 在 owner 会话、记忆预算与配置快照通过后，从共享 MCP 连接来源为当前 CurrentUser 发现请求级 MCP tools，并与 `knowledge_retrieval`、`get_current_time` 和当前 `load_skill` 同时交给 `create_agent` 自主选择。系统 MUST NOT 在模型选择前调用 MCP tool，MCP 发现失败或工具同名冲突 MUST 使本轮显式失败，不得用假结果、静态 catalog 或随机工具掩盖。

#### Scenario: 模型不调用 MCP tool
- **WHEN** 本轮已注入真实 MCP tools 但模型判断无需调用
- **THEN** 系统不执行任何 MCP tool，不发送虚假 `tool.call` 或审计

#### Scenario: 模型调用真实 MCP tool
- **WHEN** 模型选择一个当前 owner 来源中的 MCP tool
- **THEN** 真实调用产生共享 started/completed 或 started/failed `tool.call` 事件和同一 toolCallId 的 owner-scoped 审计

#### Scenario: MCP 装配失败
- **WHEN** enabled MCP Server 无法在有界重试内完成发现
- **THEN** 本轮返回共享安全错误，不调用模型、不保存半条 assistant 消息且不生成假回答
