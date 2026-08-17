## Context

参见 [proposal.md](./proposal.md) 的 Why。当前仓库已有统一 HTTP envelope/request-id、认证 CurrentUser、tenant/owner 约定、SQLAlchemy 2 async Repository 基础、请求级事务和受保护 Pinia store 清理机制；`/chat` 仍是页面占位，尚无持久化会话领域。P14 需要跨 contracts、Alembic、Repository、FastAPI 与前端 transport 建立稳定边界，同时保持 import 无 I/O，并为下一提案的流式 Agent 留出写入 assistant/tool 消息的能力。

## Goals / Non-Goals

**Goals:**

- 以规范化 SQLite 表和 Alembic migration 建立 owner-scoped 会话、消息及确定性排序。
- 用不可变 records、Repository Protocol 和 ChatService 隔离领域逻辑与 SQLAlchemy adapter。
- 让六个 API 与 TypeScript 单一事实来源、Pydantic 序列化、统一错误和 request-id 对齐。
- 在同一请求事务内完成消息写入、sequence 分配、标题派生和会话 touch。
- 建立不使用 localStorage 的 typed chatClient/Pinia store 基础。

**Non-Goals:**

- 不调用 LLM、Milvus、MCP，不生成 assistant 回复或 SSE 事件。
- 不完成 Chat 产品页面、会话侧栏交互或流式输入体验。
- 不增加多个 tenant 模型、消息编辑、分页、归档或自动清理策略。
- 不复用 background job runtime，也不创建进程内临时任务。

## Decisions

### 1. 使用独立 Chat 领域和规范化表

新增 `chat_sessions` 与 `chat_messages`，不把聊天生命周期放入通用 JSON 或 background job 表。领域层提供 frozen session/message records、Repository Protocol 与 ChatService；SQLite 实现放在 `super_ai.memory.extended_sqlite`，服务层不接收 ORM model 或 `AsyncSession`。

选择理由：会话关系、owner 查询、稳定排序、sequence 唯一性和级联删除都需要数据库约束与索引。备选的单表 JSON 对话会削弱可查询性与事务约束；background jobs 的 lease/retry 语义也不适合聊天消息。

### 2. 数据模型与索引

`chat_sessions` 包含 `id`、`owner_user_id`、有界 `title`、`created_at`、`updated_at`；新会话标题固定为“新会话”。`chat_messages` 包含 `id`、`owner_user_id`、`session_id`、`role`、非空 `content`、正整数 `sequence`、统一 JSON serializer 处理的 `metadata`、`created_at`。

`metadata` 只保存 typed `references` 与 `toolCallIds`。reference 包含 `chunkId`、`documentId`、`knowledgeBaseId`、`source` 和可选 `excerpt`；关联、排序和 owner 字段不放入 metadata。

建立 `chat_sessions(owner_user_id, updated_at, id)`、`chat_messages(owner_user_id, session_id, sequence)` 索引及 `(session_id, sequence)` 唯一约束；message 级联依赖 session，session 级联依赖 user。Alembic revision 使用 `20260817_0006`，down revision 为当前 head `20260813_0005`。

备选的全局 message sequence 会把无关会话耦合；只按 updatedAt 排序在相同时间戳时不确定，因此采用 `updated_at DESC, id DESC`。

### 3. owner scope 在每条父子 SQL 中生效

所有受保护 Repository 方法把 `owner_user_id` 作为首个业务参数。session 查询、message 查询、append、clear 和 delete 的 SQL 都包含 owner 条件；不会先按 id 无 scope 查询，再在 service 层补检查。message 同时保留 owner 列，使父子查询与删除可以在单条语句中明确表达 scope。

父 session 在 owner scope 内未命中时，无论真实不存在还是属于其他用户，均映射为 `AUTH_FORBIDDEN` 403，且不做第二次探测。这符合本 change 对受保护父资源的约定，并避免资源枚举。

### 4. append 使用单一请求事务

FastAPI 继续使用现有 `get_session`/`transaction_scope`：正常退出提交，异常回滚关闭。append 在同一事务内：owner-scoped 锁定/确认父 session、读取下一 sequence、插入 message、判断此前是否存在 user 消息、必要时生成标题并更新 updatedAt。

首条 user 标题通过 `" ".join(content.split())` 规范化空白，再截取前 48 个 Unicode 字符；是否已经生成过标题以“此前是否存在 user message”判断，而不是比较标题文字，避免首条内容恰好为“新会话”时被后续覆盖。非 user 消息不生成标题。

SQLite 会串行化写事务，数据库唯一约束是并发 sequence 的最终保护；冲突必须回滚，不允许保留半条消息或只 touch session。备选的 API 层分两次提交会产生不可恢复的部分状态，因此不采用。

### 5. clear 与 delete 保留明确不同语义

clear 在同一 owner-scoped 事务中删除子消息、把标题重置为“新会话”并 touch updatedAt，但保留 session id；下一条消息通过当前最大 sequence 为空而从 1 开始，新的首个 user 可重新派生标题。delete 删除 owner-scoped session，并由外键级联子消息，返回 `{deleted:true,sessionId}`。

不采用软删除：P14 没有恢复、审计或保留期需求，提前增加隐藏状态会复杂化每个 owner 查询。未来若需要归档/恢复，应由新规格显式扩展。

### 6. contracts 先于 API，跨语言用合同测试对齐

`packages/api-contracts` 定义 ChatSession、ChatMessage、ChatMessageMetadata、ChatReference 与六种操作的数据类型，并先把六条受保护 path 加入机器可读 manifest。所有 path 使用 `BearerAuth`、401、403；append 额外声明 validation 422。后端使用 Pydantic 对应模型，但不直接导入 TypeScript，由合同/API 测试证明 JSON 与 path 一致。

允许 `user|assistant|system|tool` role 是为了让 P15 复用同一消息模型；P14 的 append 不触发任何模型或工具。备选的 P14 只允许 user 会导致 P15 立即破坏合同，因此不采用。

### 7. 前端只建立 server-backed transport/store

新增 typed chatClient 和受保护 Pinia chatStore，复用公共 ApiClient 的 bearer、request-id 与 envelope 解包。store 管理 list、selected detail、loading/error，并在 create/append/clear/delete 后用服务端响应或重新读取结果对账。将它登记到 protected-store registry，401/logout 时只清理内存状态，不删除服务端数据。

localStorage 仍只保存认证 token；chat 数据不持久化到浏览器。P14 不改造 Chat 页面，避免把非流式临时 UI 当作最终 Agent 体验。

### 8. 依赖注入与配置公开边界保持不变

Chat Repository 由请求期数据库 session 显式创建，router 通过现有认证和 session dependencies 注入；模块 import、测试收集和 contracts 加载不打开 SQLite。Chat 不增加项目配置字段，也不读取 OS 环境变量。前端继续只接收 P01 allowlist 的 public config，聊天消息与 metadata 不进入构建期配置或浏览器 bundle 常量。

## Risks / Trade-offs

- [并发 append 竞争同一 sequence] → 使用单事务和 `(session_id, sequence)` 唯一约束；测试并发行为，冲突整体回滚而不产生部分状态。
- [消息长期增长导致详情变大] → P14 保持需求规定的完整详情；索引支持稳定读取，分页作为后续兼容扩展而不在本阶段虚构。
- [metadata 逐渐变成无结构存储] → Pydantic/TypeScript 只接受 references 与 toolCallIds；需要查询或关联的新字段必须通过后续 migration 规范化。
- [403 同时表达不存在和越权不利于内部诊断] → 客户端保持不可枚举语义；测试和安全日志可记录 request-id，但不得输出其他 owner 数据。
- [当前工作区含 P13 未提交变更] → P14 只修改明确文件，验证时区分既有 dirty changes，禁止覆盖或回退用户改动。

## Migration Plan

1. 先扩展 contracts、机器可读 path 与失败测试。
2. 新增 Alembic revision，使用临时数据库验证 fresh upgrade、downgrade/upgrade 和 metadata 一致性。
3. 实现 records、Repository Protocol、SQLite adapter、ChatService、依赖和 router，再运行 owner/事务/API 测试。
4. 实现 chatClient/store 与 protected-store 清理测试。
5. 运行全部受影响门禁、OpenSpec verify，修复问题后同步 delta specs 并归档。

回滚时先停用新路由/调用方，再 downgrade 一个 revision 删除两张新表。该 change 尚无生产聊天数据迁移来源；downgrade 会删除 P14 数据，因此只能在明确接受数据丢失的本地/开发回滚中执行。
