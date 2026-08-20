## Context

参见 [proposal.md](./proposal.md) 的动机。当前 P15 在 user 消息已经写入后，通过 `trim_chat_history` 按字符计数从最旧消息开始裁剪；P16 又在 Agent runner 内单独读取 Prompt/Skill snapshot。该路径无法在写入前计算完整候选预算，也不能形成可恢复摘要。

现有约束包括：Alembic 是 schema 唯一权威；领域层只能依赖 owner-scoped Repository Protocol 与不可变 records；模型和数据库 client 只能显式注入；Qwen chat model 的窗口必须来自 `modelCapabilities`；Prompt/Skill catalog 每轮从服务端读取且只含摘要；HTTP 与 SSE 使用共享错误模型。

## Goals / Non-Goals

**Goals:**

- 用单一请求级 memory coordinator 完成配置 snapshot、摘要高水位、候选 token 预算、自动压缩与 95% 拒绝。
- 让摘要写回、消息写入和 session DTO 投影具有明确、owner-scoped、可回滚的边界。
- 让纯估算器、摘要器、capability provider 和 Repository 均可注入，以稳定测试所有阈值和故障路径。
- 保持 P15 Agent 工具、事件、审计与成功后一次性 assistant 持久化语义。

**Non-Goals:**

- 不删除、归档或向量化完整聊天消息，不创建长期用户画像。
- 不把摘要任务放入 durable background jobs；本轮必须在接受候选消息前获得确定预算。
- 不实现 P19 composer 控件，不把任何 Chat 领域数据放入 localStorage。
- 不引入精确 tokenizer 服务、OS 环境变量配置或新的模型 SDK。

## Decisions

### 1. 记忆状态直接扩展 chat_sessions

使用 Alembic revision `20260818_0009_add_chat_session_memory.py` 为 `chat_sessions` 增加：

- `memory_mode VARCHAR(32) NOT NULL DEFAULT 'context_70_percent'`，带三值 check constraint；
- `memory_summary TEXT NULL`；
- `compacted_message_count INTEGER NOT NULL DEFAULT 0`，非负 check；
- `context_tokens INTEGER NOT NULL DEFAULT 0`，非负 check；
- `last_compacted_at UTC datetime NULL`。

`compacted_message_count` 表示已进入摘要的最大连续 message sequence，而不是累计压缩次数。消息 sequence 在会话内连续，因此它既是上下文切片高水位，也是摘要可追溯边界。`ChatSessionRecord` 扩展相同字段；不把 ORM model 或 `AsyncSession` 传给领域服务。

备选是创建 `chat_memory_snapshots` 历史表。它能保存多个摘要版本，但本提案没有恢复旧摘要或摘要审计 API，额外表会制造未被产品消费的版本语义，因此暂不采用。完整 `chat_messages` 已保留事实来源。

### 2. 纯 estimator 包装 LangChain 近似计数

新增 `super_ai.chat.memory.tokens.estimate_context_tokens(messages)`，内部只调用 `langchain_core.messages.utils.count_tokens_approximately` 并校验结果非负。领域 service 构造器接收 `TokenEstimator` callable，生产注入该纯函数，测试注入确定整数。

阈值使用 `tokens * 100 >= window * 70/95` 的整数比较；展示百分比单独计算并四舍五入到两位。这样 69/70/95 不受浮点误差或 mock 文本长度影响。

备选是使用模型 provider 的远程精确计数或继续按字符计数。前者增加网络与 provider 耦合，后者不符合统一 LangChain estimator 要求，均不采用。

### 3. 请求级 snapshot 在持久化 user 前完成

`AgentChatStreamService.prepare` 调整为：

1. owner-scoped 读取会话及消息；
2. 读取一次 P16 `ChatAgentConfigurationSnapshot`；
3. 从当前 `LlmSettings.capability_for_chat()` 取得窗口；
4. 由 memory coordinator 装配平台 Prompt、用户 Prompt、Skill catalog、摘要、未压缩消息与候选 user；
5. 按 mode 判断是否需要压缩，必要时生成/提交摘要后重新读取并估算；
6. 若达到 95%，在任何 user insert 和 Agent 调用前抛出共享 `AppError`；
7. 预算通过后，事务性保存 user 消息并把本轮不可变 configuration/memory snapshot 放入 `PreparedAgentTurn`。

runner 不再自行读取可能变化的 configuration；`ConfiguredAgentTurnRunner` 接受 prepare 阶段固定的 snapshot/system prompt。这样预算所见与模型实际输入一致，配置在进行中的轮次不会漂移。

备选是在写入 user 后再预算并在超限时删除该消息。这会破坏 sequence/标题事务语义且不满足“拒绝前不持久化”，不采用。

### 4. 压缩只覆盖完整 turn，并以条件更新防止过期写回

memory coordinator 从高水位后按 sequence 扫描，仅把最后一个形成完整 user/assistant 配对的 assistant sequence 作为目标高水位。`every_30_turns` 统计自高水位后的完整配对；`context_70_percent` 使用候选预算；`manual` 只有 compact API 进入摘要路径。

摘要器接收旧摘要与目标边界内的新消息，调用注入的 `BaseChatModel.ainvoke`，要求返回非空文本。LLM 调用不持有 SQLite transaction。成功后 Repository 执行同时包含 owner、session id、预期旧高水位与目标 message boundary 的条件更新；若影响行数为 0，说明并发状态已改变，丢弃过期摘要并重新读取，不覆盖新状态。失败不更新摘要、高水位、token 或时间。

备选是把 LLM 调用放进数据库事务以锁住会话。网络调用会长期占用 SQLite 写锁并放大失败影响，不采用。

### 5. 上下文由统一 assembly 产生

把 P16 的平台规则、用户 Prompt 与 Skill catalog 装配拆成可复用纯函数，memory coordinator 和 Agent runner消费同一 system prompt。模型 messages 顺序为：

1. 一个 system message，包含平台安全规则、当前 Prompt 与 Skill catalog；
2. 若存在摘要，增加一个明确标注“历史摘要/低于系统规则”的 system message；
3. 高水位之后的原始 LangChain messages；
4. 尚未落盘的候选 user message（prepare 估算）或已落盘同一 user message（runner 执行）。

已压缩逐条消息不再送模型，完整 SQLite 历史仍由详情 API 返回。P15 `trim_chat_history` 从生产路径移除，避免两种算法叠加。Skill 正文仍只由 `load_skill` 真实调用后进入该次 Agent tool message。

### 6. DTO 刷新与 context_tokens 缓存

`context_tokens` 是最近一次估算缓存，不是不可变事实。会话详情、记忆 mutation 与 stream prepare 使用 memory projector 按当前 Prompt/Skill snapshot 和 capability 重算，并以 owner-scoped 更新保存。列表 API 为 owner 的每个 session 计算投影后返回，保证 Prompt/Skill 变化后的 DTO 不沿用陈旧百分比；本地单用户和当前会话规模下优先保证语义正确，后续如有性能压力再做批量查询优化。

`canCompact` 由消息高水位后是否存在完整 turn 计算，不能仅凭 message count 猜测。缺少 capability 抛出 `SYSTEM_MODEL_CAPABILITY_MISSING`，不回退到 1 或任意默认窗口。

### 7. HTTP/SSE 错误与 API 形状

共享 manifest、TypeScript 和 Pydantic 增加：

- `ChatMemoryMode`、扩展后的 `ChatSession`、`UpdateChatMemoryRequest`；
- `PUT /chat/sessions/{id}/memory`；
- `POST /chat/sessions/{id}/memory:compact`；
- `CHAT_CONTEXT_LIMIT_REACHED`（business/409）；
- `SYSTEM_MODEL_CAPABILITY_MISSING`（system/500）。

预算通常在 `StreamingResponse` 创建前失败，因此返回标准 HTTP failure envelope；流内防御性检查若发现相同错误则通过 `AgentEventMapper.error` 发送同一个 `ApiErrorModel`。`AppError` 到 SSE error 的 mapper 只查共享目录，不复制 code/status/message。

### 8. 前端只扩展 typed client/store

`chatClient` 增加两个方法，Pinia store 增加对应 action，并在响应后同时更新 sessions 中的投影与 selected detail。现有 401 handler 和 protected store cleanup 继续负责清理。P17 不改 workspace 布局或增加控制组件。

## Risks / Trade-offs

- [摘要可能遗漏原文细节] → 原始消息完整保留；摘要 prompt 要求关键事实与引用 id，可重复手动压缩并通过高水位追溯来源。
- [并发流式轮次竞争 sequence 或摘要] → 条件写回高水位；user append 继续在 session 行事务边界内分配 sequence；过期摘要不得覆盖。
- [Prompt/Skill 更新使已缓存 token 失效] → session 读、记忆操作和 stream prepare 均从当前 snapshot 重算；`context_tokens` 明确定义为可重算缓存。
- [列表逐会话投影带来额外查询] → 先保证本地桌面产品正确性；Repository 采用批量加载 owner messages，避免 N+1，后续可在不改合同的情况下优化。
- [近似 token 计数与模型真实 tokenizer 有误差] → 95% 而非 100% 作为硬上限留出安全余量；不声称精确 token 计费。
- [摘要 LLM 失败阻塞自动模式的新轮次] → 保持数据库原状态并返回安全错误，不以静默裁剪或假摘要降级；用户可稍后重试。

## Migration Plan

1. 先更新共享 contracts/manifest 与测试，再增加 Alembic revision、ORM/record/Repository 字段和迁移一致性测试。
2. 对已有 `chat_sessions` 使用 server default 回填默认模式、0 高水位和 0 token；迁移后保留默认约束以覆盖非应用写入。
3. 先接入纯 estimator、memory service/summary adapter 和 API，再替换 stream prepare/runner 的旧裁剪路径。
4. 更新前端 client/store，运行完整门禁后同步 delta specs 并归档。
5. downgrade 删除新增列与约束，不触碰 `chat_messages`。若应用回滚到 P16，既有完整历史仍可正常读取；P17 派生摘要不可用但没有历史数据损失。
