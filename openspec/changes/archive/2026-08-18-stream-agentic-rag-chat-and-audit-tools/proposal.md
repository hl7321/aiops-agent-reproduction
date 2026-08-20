## Why

P14 已建立服务端会话与消息生命周期，P12 已提供 tenant-safe 知识检索工具，但两者尚未形成由模型自主选择工具、可实时反馈且可审计的 Agent 对话闭环。现在需要建立稳定的流式执行与持久化边界，作为后续 MCP 工具扩展和完整 Chat 工作区的基础。

## What Changes

- 新增基于 LangChain 1.x `create_agent` 的聊天运行时，由模型在 `knowledge_retrieval` 与 `get_current_time` 之间自主选择，禁止每轮固定先检索。
- 新增 owner-scoped 流式消息 API，并通过共享 SSE union 输出正文、真实 reasoning、工具生命周期、引用、完成或安全错误事件。
- 建立一致的消息事务语义：Agent 开始前持久化 user 消息，只有成功完成后才一次性持久化 assistant 消息及本轮引用/工具调用标识。
- 新增通用 Agent 工具调用审计迁移、Repository、生命周期记录和会话审计查询 API，同时约束日志不得复制敏感参数值、prompt、query、工具输出或 token。
- 扩展共享 contracts、OpenAPI、前端 typed stream transport 与 Chat store 的实时状态基础。
- 增加事件顺序、Unicode 字符拆分、工具自主调用、引用隔离、失败一致性、审计生命周期和跨租户验收测试。
- 不在本 change 接入 MCP，不实现 durable Agent generation、HTTP Last-Event-ID 恢复或完整 Chat 页面。

## Capabilities

### New Capabilities

- `agentic-rag-chat-streaming`：定义模型自主选工具、owner-scoped 流式执行、SSE 顺序与消息持久化语义。
- `agent-tool-call-auditing`：定义通用工具调用审计记录、父对象约束、安全日志与 owner-scoped 查询。

### Modified Capabilities

- `api-and-sse-contracts`：为共享 SSE 公共字段增加稳定 sequence，并增加聊天流与工具审计的 DTO/OpenAPI 合同。
- `chat-session-management`：在既有服务端会话生命周期上增加流式消息、成功后 assistant 持久化与逐轮引用隔离要求。

## Impact

- 后端新增 Agent runner、事件映射、工具工厂、审计领域与 SQLite adapter，并扩展 Chat service/router/dependencies。
- Alembic 新增 `agent_tool_call_audits` 表；chat parent 使用现有会话外键，diagnostic parent 为后续 AIOps 保留受约束标识。
- `packages/api-contracts` 扩展 Chat、SSE 和 OpenAPI 类型；前端 transport/store 消费同一 event union。
- 运行时复用 P06 Qwen provider、P12 knowledge tool、P14 chat Repository 和现有认证/tenant scope；测试使用可注入 fake，不依赖真实外部服务。
