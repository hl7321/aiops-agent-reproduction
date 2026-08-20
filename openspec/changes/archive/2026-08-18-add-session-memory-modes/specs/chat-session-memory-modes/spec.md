## Purpose

本能力为每个 owner-scoped 聊天会话提供可持久恢复、可显式控制且不会破坏完整历史的记忆压缩策略，并在模型上下文达到安全硬上限前稳定拒绝新轮次。

## ADDED Requirements

### Requirement: 每个会话独立持久化记忆状态
系统 SHALL 为每个会话保存 `memoryMode`、nullable `memorySummary`、`compactedMessageCount`、`contextTokens` 与 nullable `lastCompactedAt`，默认模式 MUST 为 `context_70_percent`。允许的模式 MUST 仅为 `every_30_turns`、`context_70_percent`、`manual`。所有记忆读写 MUST 同时按当前 owner 与 session id 限定，且一个会话的更新 MUST NOT 改变同 owner 或其他 owner 的其他会话。

#### Scenario: 创建默认记忆状态
- **WHEN** 已认证用户创建新会话
- **THEN** 会话使用 `context_70_percent`，摘要为空、高水位和 contextTokens 为 0、lastCompactedAt 为空

#### Scenario: 两个会话使用不同模式
- **WHEN** 同一用户分别把两个会话更新为 `manual` 与 `every_30_turns`
- **THEN** 再次读取时每个会话保留自己的模式与压缩状态，互不影响

#### Scenario: 跨用户修改记忆
- **WHEN** 用户 B 更新或压缩用户 A 的会话记忆
- **THEN** 系统返回与父会话不可见一致的 `AUTH_FORBIDDEN` 403，且用户 A 的记忆和消息保持不变

### Requirement: 会话 DTO 返回刷新后的记忆投影
每个 Chat session DTO SHALL 返回 `memoryMode`、`memorySummary`、`contextTokens`、`contextWindowTokens`、`contextUsagePercent`、`compactedMessageCount`、`lastCompactedAt` 与 `canCompact`。`contextWindowTokens` MUST 来自当前 chat model capability；`contextUsagePercent` MUST 由 token 用量与窗口计算；`canCompact` MUST 只在存在尚未压缩的完整 user/assistant turn 时为 true。读取详情、记忆写操作和流式轮次 MUST 使用当前 Prompt/Skill catalog 刷新预算投影。

#### Scenario: 返回可压缩会话状态
- **WHEN** 会话包含至少一个未压缩的完整 user/assistant turn
- **THEN** DTO 返回正确窗口、用量百分比、高水位和 `canCompact=true`

#### Scenario: 当前模型缺少 capability
- **WHEN** 当前 chat model 没有正整数 `contextWindowTokens` profile
- **THEN** 系统在创建模型 client 或猜测窗口前返回明确、脱敏的 `SYSTEM_MODEL_CAPABILITY_MISSING`

### Requirement: token 估算具有单一可测试语义
系统 SHALL 通过一个纯 token 估算边界计算待发送 LangChain messages 的近似 token 数；生产估算 MUST 使用 LangChain `count_tokens_approximately`，且阈值决策 MUST 允许测试注入确定估算结果。阈值比较 MUST 使用未舍入 token 数，不能因展示百分比舍入改变边界结果。

#### Scenario: 69% 不触发 70% 阈值
- **WHEN** 注入估算结果等于 context window 的 69%
- **THEN** `context_70_percent` 模式不因该预算触发自动压缩

#### Scenario: 70% 触发压缩
- **WHEN** 注入估算结果恰好等于 context window 的 70%
- **THEN** `context_70_percent` 模式触发自动压缩

#### Scenario: 95% 触发硬上限
- **WHEN** 压缩后或未启用自动压缩的候选预算恰好等于 context window 的 95%
- **THEN** 系统执行硬上限拒绝而不是继续保存消息或调用 Agent

### Requirement: 三种模式按完整轮次触发压缩
`every_30_turns` SHALL 在自当前压缩高水位之后累积至少 30 个完整 user/assistant turn 时自动压缩，29 个完整 turn MUST NOT 触发；`context_70_percent` SHALL 在包含候选 user 消息的预计上下文达到 70% 时自动压缩；`manual` MUST 只响应显式压缩 API，流式请求不得自动压缩。压缩边界 MUST 结束于完整 assistant 消息，尾部未完成 user 消息不得进入摘要。

#### Scenario: 第 29 个完整轮次
- **WHEN** `every_30_turns` 会话自高水位后只有 29 个完整 turn
- **THEN** 下一轮预算未达到硬上限时系统不自动生成摘要

#### Scenario: 第 30 个完整轮次
- **WHEN** `every_30_turns` 会话自高水位后达到 30 个完整 turn
- **THEN** 系统在接受下一轮前自动压缩这些完整 turn 并推进高水位

#### Scenario: manual 模式达到 70%
- **WHEN** `manual` 会话的候选预算达到 70% 但低于 95%
- **THEN** 系统不自动压缩并可继续该轮

### Requirement: 压缩生成可追溯摘要且保留完整历史
系统 SHALL 调用可注入 chat LLM，以旧摘要与高水位之后的完整轮次生成新摘要，并用摘要、新高水位和 `lastCompactedAt` 表示其来源边界。压缩 MUST NOT 删除、改写、重排或隐藏任何 `chat_messages`。外部摘要失败或写回冲突 MUST NOT 提交部分摘要、高水位或时间更新。

#### Scenario: 成功压缩历史
- **WHEN** 会话有可压缩的完整轮次且摘要模型成功返回
- **THEN** 系统更新摘要、高水位与时间，但详情仍返回压缩前后的全部原始消息及原 sequence

#### Scenario: 摘要模型失败
- **WHEN** 摘要调用失败
- **THEN** 记忆摘要、高水位、token 投影和原始消息保持调用前状态，并返回安全错误

#### Scenario: 并发状态已经变化
- **WHEN** 摘要生成期间相同会话的高水位或目标消息边界被另一写操作改变
- **THEN** 系统不得用过期摘要覆盖新状态

### Requirement: 模型上下文使用摘要与未压缩消息
系统 SHALL 按平台安全规则、当前用户 Prompt、选中 Skill name/description catalog、可用历史摘要、压缩高水位之后的消息和当前候选 user 消息装配模型上下文。系统 MUST NOT 把已进入摘要的历史消息再次作为逐条消息发送，也 MUST NOT 预注入 Skill 正文。

#### Scenario: 已压缩会话继续对话
- **WHEN** 会话存在摘要、高水位和高水位之后的新消息
- **THEN** 模型输入包含摘要和新消息，不重复包含高水位以内的逐条历史

#### Scenario: 不同会话的摘要
- **WHEN** 同一用户在会话 A 与 B 中分别对话
- **THEN** 会话 A 的模型输入绝不包含会话 B 的摘要或消息

### Requirement: 95% 硬上限在 user 消息持久化前生效
系统 SHALL 在持久化候选 user 消息和调用模型之前计算完整候选预算；执行当前模式允许的自动压缩后，若预算达到 context window 的 95%，系统 MUST 返回 `CHAT_CONTEXT_LIMIT_REACHED`，提示手动压缩，且 MUST NOT 保存该 user 消息、调用 Agent 或生成假回答。

#### Scenario: manual 模式达到硬上限
- **WHEN** manual 会话的候选预算达到 95%
- **THEN** HTTP 返回共享 409 failure envelope，详情中的消息与记忆状态不包含候选消息

#### Scenario: 自动压缩后仍达到硬上限
- **WHEN** 自动压缩成功但新摘要与剩余上下文的候选预算仍达到 95%
- **THEN** 系统返回相同 `CHAT_CONTEXT_LIMIT_REACHED`，不持久化候选 user 消息

#### Scenario: SSE 已开始后的同类保护错误
- **WHEN** 流开始后检测到必须终止的上下文上限错误
- **THEN** SSE `error` 事件复用 HTTP 错误的 code、category、httpStatus、message 和 details 形状

### Requirement: 记忆 API 更新模式并显式压缩
系统 SHALL 提供 `PUT /chat/sessions/{id}/memory` 接受有效 `memoryMode`，以及 `POST /chat/sessions/{id}/memory:compact` 显式压缩当前完整未压缩轮次；两者 MUST 返回刷新后的 `ChatSessionDetailData`。没有可压缩完整轮次时，显式压缩 MUST 幂等返回当前状态。

#### Scenario: 更新会话记忆模式
- **WHEN** owner 把会话模式更新为 `manual`
- **THEN** 响应详情立即返回 `memoryMode=manual` 和按当前配置刷新的记忆投影

#### Scenario: 手动压缩空边界
- **WHEN** 会话没有尚未压缩的完整 turn 而 owner 调用 compact
- **THEN** 系统不调用摘要模型并返回未损坏的当前详情

### Requirement: 前端记忆状态只与服务端对账
前端 typed chat client/store SHALL 支持读取 session 记忆字段、更新模式和手动压缩，并在成功后以服务端详情替换对应 session/message 状态。记忆状态 MUST NOT 保存到 localStorage；认证失效或 logout MUST 沿用受保护 store 清理。P17 MUST NOT 声称 P19 composer 控件已完成。

#### Scenario: 前端更新模式
- **WHEN** store 调用更新模式并收到成功 envelope
- **THEN** store 用响应中的完整详情更新当前会话和列表投影

#### Scenario: 认证失效清理记忆
- **WHEN** 记忆 API 返回 401 或用户登出
- **THEN** store 清除内存中的会话记忆状态但不删除服务端会话或历史
