## Why

当前 `/chat` 尚无服务端会话与消息生命周期，后续流式 Agent 若直接落地会被迫自造临时状态和 payload。现在需要先建立 owner-scoped、可事务验证的 SQLite 会话边界，让客户端刷新、跨请求和后续流式处理都以服务端数据为事实来源。

## What Changes

- 在共享 contracts 与机器可读 OpenAPI 目录中定义聊天会话、消息、结构化 metadata、列表/详情/创建/追加/清空/删除合同，并复用统一 envelope、BearerAuth、401 与 403。
- 通过 Alembic 新增 `chat_sessions` 与 `chat_messages`，建立 owner-scoped Repository record/Protocol 和 SQLite adapter；服务层不接收 ORM model。
- 实现会话与消息 API；首条用户消息生成有界标题，列表使用确定性倒序，消息写入与会话更新时间在同一事务边界。
- 实现清空消息并重置衍生状态，以及级联删除当前用户会话；资源不存在与跨用户父资源访问统一返回 `AUTH_FORBIDDEN`，不通过无 scope 查询探测资源。
- 增加前端 typed `chatClient` 和受保护 Pinia `chatStore` 基础，以服务端为事实来源且不把聊天领域数据写入 localStorage。
- 本 change 不调用模型、不实现 SSE 流式 Agent、不完成聊天产品页面，也不引入临时进程内状态。

## Capabilities

### New Capabilities

- `chat-session-management`: 定义 owner-scoped 会话与消息的持久化、事务、标题、排序、清空、删除、API 和前端状态边界。

### Modified Capabilities

- `api-and-sse-contracts`: 增加聊天 DTO、metadata、机器可读受保护路径和前后端合同一致性要求。

## Impact

- 后端：`apps/backend/migrations/versions`、`super_ai.chat`、`super_ai.memory.extended_sqlite`、应用依赖与路由注册、相关测试。
- 合同：`packages/api-contracts` 的聊天类型、OpenAPI path 目录、错误与合同测试。
- 前端：`apps/frontend/src/chat`、受保护 Pinia store 注册与测试；不改变现有 `/chat` 页面产品范围。
- 数据：新增 SQLite 规范化表、外键和索引；Alembic 仍是 schema 唯一权威。
- 安全：所有读取、写入、清空和删除均在 SQL 查询中显式包含 `owner_user_id`，不扩大 tenant 权限。
