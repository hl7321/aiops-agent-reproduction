# P17 会话记忆模式设计

## 目标与非目标

P17 为每个聊天会话建立独立、持久、owner-scoped 的记忆压缩状态。完整
`chat_messages` 始终是审计与恢复的事实来源；压缩只生成供模型使用的派生摘要，绝不删除、
覆盖或改写历史消息。本变更不实现 P19 的 composer UI，也不引入向量化会话记忆、长期用户画像
或新的后台任务运行时。

## 推荐架构

在 `chat_sessions` 上保存 `memory_mode`、`memory_summary`、
`compacted_message_count`、`context_tokens`、`last_compacted_at`。其中
`compacted_message_count` 是已经进入摘要的消息 sequence 高水位；摘要、该高水位与压缩时间共同构成
可追溯的派生状态。原始消息继续完整保存在 `chat_messages`。

新增三个互相解耦的服务边界：

1. 纯 token 预算器：`estimate_context_tokens` 内部调用 LangChain
   `count_tokens_approximately`，只接收待发送的 LangChain messages 并返回非负整数。上层服务允许注入
   estimator，测试因此可以精确覆盖 69%、70% 与 95%。
2. owner-scoped 记忆服务：加载会话、当前 Prompt/Skill 快照和当前模型 capability，决定是否压缩、
   生成模型上下文并持久化最新 token 投影。Repository 方法始终以 `owner_user_id` 为第一个业务参数。
3. 可注入摘要器：显式调用当前 chat model，根据旧摘要与新增的完整轮次生成新摘要。摘要失败时不更新
   会话记忆状态；外部调用期间不持有 SQLite 事务，写回时使用预期高水位做条件更新，避免并发覆盖。

P15 的 `trim_chat_history` 将退出主执行路径，避免旧的“直接丢弃最旧模型输入”与 P17 的摘要高水位
同时生效。Agent runner 在同一个请求快照中消费系统 Prompt、Skill catalog、历史摘要与未压缩消息。

## 数据与状态语义

- `memory_mode` 取 `every_30_turns | context_70_percent | manual`，新会话默认
  `context_70_percent`。
- `memory_summary` 为 nullable 文本；没有已压缩消息时为 null。
- `compacted_message_count` 是已纳入摘要的最大连续 message sequence，初始为 0。压缩边界只落在
  完整 user/assistant turn 末尾，不压缩尾部未完成的 user 消息。
- `context_tokens` 保存最近一次按当前 Prompt/Skill catalog、摘要和未压缩消息得到的估算值；会话读取、
  记忆写操作和新流式轮次都会刷新它。它是可重算缓存，不是原始事实。
- `last_compacted_at` 只在摘要成功提交时更新。
- `contextWindowTokens` 来自当前 chat model 的 `modelCapabilities`。缺失 profile 时返回明确且脱敏的
  `SYSTEM_MODEL_CAPABILITY_MISSING`，绝不猜测窗口。
- `contextUsagePercent = contextTokens / contextWindowTokens * 100`，返回保留两位小数的数值。
- `canCompact` 仅在当前会话存在至少一个尚未纳入摘要的完整 user/assistant turn 时为 true。

清空会话时，除消息与标题外，同时把摘要、高水位、token 缓存和最后压缩时间恢复初始值；删除会话
继续依赖父记录级联删除消息。

## 自动压缩与硬上限

每次流式请求先校验 owner，再加载当前 Prompt/Skill 快照、模型 capability 和会话历史，但尚不保存新
user 消息。候选预算包含平台规则、当前 Prompt、Skill name/description catalog、历史摘要、未压缩消息
和本次候选 user 消息。

- `every_30_turns`：自上次高水位后正好达到或超过 30 个完整 user/assistant turn 时自动压缩；29 个
  turn 不触发。若不足 30 turn 却先达到 95%，拒绝并提示手动压缩。
- `context_70_percent`：候选预算达到窗口的 70%（含边界）时先自动压缩，再重新估算。
- `manual`：流式请求永不自动压缩，只能调用显式 compact API。
- 所有模式在自动压缩完成或跳过后重新估算；候选预算达到 95%（含边界）时返回
  `CHAT_CONTEXT_LIMIT_REACHED` 409，并且不保存候选 user 消息、不调用 Agent。

阈值使用整数交叉乘法比较，避免浮点舍入把 69%/70%/95% 边界判断错位。压缩自身生成的摘要仍可能
过长；重新估算后若仍达到 95%，同样安全拒绝。

## 摘要生成与一致性

摘要输入只包含旧摘要和高水位之后、最近完整 turn 末尾之前的消息。摘要 prompt 要求保留关键事实、
决定、未解决事项、工具结论和引用标识，但不得伪造事实。日志只记录 owner/session 的安全标识、消息
数量、耗时和结果状态，不记录 prompt、消息正文或摘要正文。

流程分为读取快照、LLM 摘要、条件写回三段。LLM 失败时数据库零变化；条件写回发现高水位或消息
边界已变化时拒绝覆盖并重新读取，不写入过期摘要。摘要成功后再刷新 token 投影。SQLite 与外部 LLM
之间不宣称跨系统事务。

## API 与合同

扩展 `ChatSession` DTO，增加：

- `memoryMode`
- `memorySummary`
- `contextTokens`
- `contextWindowTokens`
- `contextUsagePercent`
- `compactedMessageCount`
- `lastCompactedAt`
- `canCompact`

新增：

- `PUT /chat/sessions/{id}/memory`，请求 `{memoryMode}`，更新模式并返回刷新后的
  `ChatSessionDetailData`。
- `POST /chat/sessions/{id}/memory:compact`，无请求体，显式压缩完整未压缩轮次并返回刷新后的
  `ChatSessionDetailData`；没有可压缩完整轮次时返回幂等的当前详情。

两个端点沿用 bearer、401/403/422。`CHAT_CONTEXT_LIMIT_REACHED` 属于 business/409，默认安全消息为
“会话上下文已达到安全上限，请先手动压缩记忆”。在 HTTP response 尚未开始时使用失败 envelope；若
流已经开始后同类保护错误才被发现，则 SSE `error` 复用同一个 `ApiErrorModel`，不得生成另一套错误。

## 前端边界

共享 contracts 增加记忆模式、DTO 字段、请求与 OpenAPI operation。`chatClient` 和 Pinia chat store
提供 `updateMemoryMode` 与 `compactMemory`，总是以服务端返回详情对账；认证失效沿用统一清理机制，
不把任何记忆状态放入 localStorage。P17 不添加最终可视化控件，P19 再把这些动作接入 composer。

## 验证策略

先写失败测试，再逐层实现：迁移/metadata、Repository owner scope 与条件写回、纯 estimator、三模式
边界、摘要成功与失败、不可变历史、95% 拒绝前不落 user 消息、HTTP/SSE 错误复用、capability 缺失、
前端 typed client/store。最后运行 migration、backend Ruff/Pyright/pytest、contracts 与 frontend 全门禁、
`openspec validate --all` 和 `git diff --check`。
