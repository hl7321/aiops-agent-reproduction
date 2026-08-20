## Why

当前流式 Chat 只按固定窗口丢弃最旧的模型输入，既不能让用户选择压缩策略，也没有可持久恢复的摘要与上下文用量；长会话可能在模型硬上限附近才以不稳定方式失败。现在需要在保留完整消息历史的同时，为每个会话建立可追溯、可测试且安全拒绝超限请求的记忆边界。

## What Changes

- 为每个 owner-scoped Chat session 增加 `every_30_turns`、`context_70_percent`、`manual` 三种独立记忆模式，以及摘要、高水位、token 投影和最后压缩时间。
- 以 Alembic 扩展 `chat_sessions`；完整 `chat_messages` 永远保留，压缩只更新派生摘要，不删除或改写历史。
- 建立使用 LangChain `count_tokens_approximately` 的纯 token 估算入口，并允许测试注入确定结果以覆盖 69%/70%/95% 边界。
- 由可注入 LLM 摘要器生成可追溯摘要；按 30 个完整轮次或 70% 候选预算自动压缩，manual 模式只允许显式压缩。
- 在保存候选 user 消息和调用 Agent 之前执行预算检查；达到 95% 时使用共享 `CHAT_CONTEXT_LIMIT_REACHED` 阻止本轮且不落消息。
- 用“历史摘要 + 未压缩消息 + 当前 Prompt/Skill catalog”替代 P15 的最旧消息裁剪，缺少当前模型 capability 时返回明确配置错误。
- 新增更新记忆模式和手动压缩 API，扩展 session DTO、共享 contracts、OpenAPI 与前端 chat client/store；最终 composer 控件留给 P19。
- 以迁移、owner scope、三模式阈值、摘要回滚、历史不变、HTTP/SSE 错误一致和前端对账测试建立门禁。

## Capabilities

### New Capabilities

- `chat-session-memory-modes`: 定义会话级记忆状态、token 预算、三种压缩策略、显式压缩 API、硬上限和前端 typed 状态边界。

### Modified Capabilities

- `chat-session-management`: 扩展持久化会话 DTO、清空衍生状态、owner-scoped 记忆更新与前端服务端对账语义。
- `agentic-rag-chat-streaming`: 把旧历史裁剪替换为摘要与未压缩消息装配，并在落 user 消息前执行 95% 保护及共享 HTTP/SSE 错误。
- `prompt-and-progressive-skill-management`: 要求当前 Prompt 与 Skill catalog 和会话记忆在同一请求快照中参与上下文装配与预算。
- `api-and-sse-contracts`: 增加记忆 DTO、两条 OpenAPI path、稳定错误及 HTTP/SSE 错误复用合同。

## Impact

- 后端：Alembic/SQLAlchemy Chat session schema、不可变 records、Repository Protocol/SQLite adapter、Chat service/router/dependencies、Agent stream/history/configuration assembly、错误目录与测试。
- contracts：Chat memory 类型、session DTO、请求、OpenAPI manifest/operations、错误目录与合同测试。
- 前端：typed `chatClient`、Pinia chat store 及其认证清理和对账测试；不新增 P19 最终 UI。
- 模型：复用当前 Qwen chat model 与 `modelCapabilities.contextWindowTokens`；不新增 SDK、配置源或 import-time client。
- 安全：所有读写继续显式 owner scope；日志不记录 prompt、消息或摘要正文；缺失 capability、摘要失败与超限均不得以猜测或静默裁剪降级。
