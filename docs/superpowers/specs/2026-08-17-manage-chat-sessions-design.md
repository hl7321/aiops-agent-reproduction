# 服务端聊天会话管理设计

## 目标与范围

P14 建立完全由服务端 SQLite 管理的聊天会话与消息生命周期，为后续流式 Agent 提供稳定、owner-scoped 的持久化边界。本阶段不调用模型、不生成流式事件、不实现 Chat 产品页面，也不把会话或消息存入浏览器 localStorage。

## 架构方案

采用独立 Chat 领域边界：领域层提供不可变 session/message record、Repository Protocol 和 ChatService；SQLite adapter 位于 `super_ai.memory.extended_sqlite`；FastAPI router 只负责认证上下文、合同转换和统一 envelope；TypeScript contracts 是前端请求/响应和 OpenAPI path 的单一事实来源。

不采用通用事件表，因为会把会话关系、排序和查询需求压入无结构 JSON；不复用 background jobs，因为聊天消息与任务租约、重试和运行状态具有不同生命周期。

## 数据模型

`chat_sessions` 使用规范化列保存：

- `id`：32 字符项目 ID。
- `owner_user_id`：必填外键，级联用户删除。
- `title`：必填、有界字符串；新建时为“新会话”。
- `created_at`、`updated_at`：UTC 时间。

`chat_messages` 使用规范化列保存：

- `id`：32 字符项目 ID。
- `owner_user_id`：必填 owner scope，与 session owner 同义但独立保留以支持单语句 scope。
- `session_id`：指向 `chat_sessions.id`，会话删除时级联删除。
- `role`：`user | assistant | system | tool`。
- `content`：非空文本。
- `sequence`：会话内从 1 开始的正整数，`session_id + sequence` 唯一。
- `metadata`：统一 JSON 序列化的 typed 对象。
- `created_at`：UTC 时间。

metadata 只允许合同定义的结构：可选 `references` 和 `toolCallIds`。reference 包含稳定 `chunkId`、`documentId`、`knowledgeBaseId`、`source` 和可选 `excerpt`；`toolCallIds` 是非空字符串数组。默认 metadata 是空对象，不在其中保存会话状态、排序字段或可查询关联。

索引至少覆盖 `chat_sessions(owner_user_id, updated_at, id)`、`chat_messages(owner_user_id, session_id, sequence)`，并为会话内 sequence 建立唯一约束。

## 领域行为与事务

所有 Repository 方法的首个业务参数是 `owner_user_id`，所有读取、更新和删除 SQL 在同一语句中包含 owner scope。服务层只接收 Repository Protocol 和不可变 record，不接收 ORM model 或 `AsyncSession`。

新建会话创建空 session，标题为“新会话”。追加消息时，Repository 在当前请求事务中按 owner scope 确认父 session、计算下一 sequence、写入 message，并更新 session：

- 第一条 `user` 消息将连续空白折叠为单个空格，去除首尾空白，然后截取最多 48 个 Unicode 字符作为标题。
- assistant/system/tool 消息不会生成标题；后续 user 消息也不会覆盖已有派生标题。
- 每条成功追加都会更新 session `updated_at`。
- 列表使用 `updated_at DESC, id DESC`，以 ID 作为相同时间戳下的确定性 tie-breaker。

clear 在同一事务中删除当前 owner/session 的全部消息，将标题恢复为“新会话”并更新 `updated_at`。清理后的下一条消息重新从 sequence 1 开始，并可再次从第一条 user 消息生成标题。

delete 使用 owner-scoped session 删除，数据库外键级联删除子消息。任何父 session 未在当前 owner scope 命中时都返回 `AUTH_FORBIDDEN` 403；不存在 ID 与跨用户 ID 使用相同响应，不执行无 scope 的第二次存在性查询。

请求事务继续复用 `get_session` 和 `transaction_scope`：正常退出提交，异常回滚。追加消息的 message insert 与 session touch 不允许拆成两个请求或两个事务。

## HTTP 与合同

受保护 API：

- `POST /chat/sessions`：创建空会话。
- `GET /chat/sessions`：按稳定倒序返回会话摘要。
- `GET /chat/sessions/{id}`：返回 session 与按 sequence 升序的消息。
- `POST /chat/sessions/{id}/messages`：追加一条 typed message。
- `POST /chat/sessions/{id}/messages:clear`：清空消息并返回重置后的详情。
- `DELETE /chat/sessions/{id}`：返回 `{deleted: true, sessionId}`。

共享 contracts 定义 `ChatSession`、`ChatMessage`、`ChatMessageMetadata`、reference、list/detail/create/append/clear/delete DTO，并把六条 path 加入机器可读 OpenAPI manifest。所有路径复用 bearer、401、403、统一 envelope 和 `X-Request-ID`。

append request 允许 `user | assistant | system | tool`，为 P15 的服务端 Agent 写入保留同一稳定领域合同；P14 不根据 role 调用任何模型或工具。

## 前端基础

新增 typed `chatClient` 和受保护 Pinia `chatStore`：

- 从服务端加载 session list/detail；
- 创建、选择、追加、clear、delete 后以服务端响应和重新读取结果对账；
- 401/logout 通过 protected-store registry 清空全部会话、消息、选择和错误状态；
- localStorage 仍只允许认证 token，Chat 数据只在内存中短暂缓存；
- 不在 P14 改造 Chat 页面，也不实现流式 transport 或模型交互。

## 错误与安全

- 未认证统一 `AUTH_REQUIRED` 401。
- session 不在当前 owner scope 统一 `AUTH_FORBIDDEN` 403。
- 空 content、非法 role、超过合同上限的 title/content/metadata 字段统一由 Pydantic/FastAPI 映射为 `VALIDATION_REQUEST_INVALID` 422。
- API 与日志不输出其他 owner 的 session、message 或 metadata。
- 模块 import、测试收集和 contracts 加载不得连接 SQLite 或任何外部服务。

## 测试与验收

按 TDD 顺序先补 contracts 与迁移失败测试，再实现最小代码。后端测试使用临时 SQLite，覆盖：

- fresh migration 与 ORM metadata 一致；
- 两个用户 CRUD 和所有父子 owner scope；
- updatedAt 倒序与 ID tie-breaker；
- 第一条 user 自动标题、48 字符边界和空白规范化；
- role/content、sequence、UTC 时间、references/toolCallIds round-trip；
- append 中任一步失败时 message 与 session 更新共同回滚；
- clear 重置标题、消息和 sequence；
- delete cascade；
- 不存在和跨用户 session 的一致 403 envelope；
- request-id、401、403 和 OpenAPI 合同形状。

前端测试覆盖 bearer/envelope、list/detail/create/append/clear/delete 对账、选择状态和 protected-store 清理，证明没有把 Chat 领域数据写入 localStorage。

最终运行 Alembic upgrade、backend Ruff/strict Pyright/pytest、contracts typecheck/test、frontend typecheck/test/build、`openspec validate --all` 与 `git diff --check`。验证通过且 `openspec-verify-change` 无 CRITICAL 后，才同步 delta specs 并归档。
