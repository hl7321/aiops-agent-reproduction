## Context

P14/P15 已把 Chat message 与引用 metadata 持久化，P21/P23 已把 diagnostic step/report 和桌面 AIOps 工作区落地。P24 要在这些现有真实目标上增加统一反馈，而不是建立不受约束的通用评论表。反馈包含用户评价、评论和纠正，既需要跨页面复用，也必须避免客户端伪造 owner 或借错误语义枚举其他用户资源。

项目继续使用 Python >=3.10、FastAPI、Pydantic v2、SQLAlchemy 2 async、aiosqlite、Alembic、pytest/Ruff/strict Pyright，以及 Vue 3.5、TypeScript 5.6 strict、Pinia 3、Vitest 2。配置仍来自本地 JSON 深合并；本 change 不增加配置项、外部服务或 import-time I/O。

## Goals / Non-Goals

**Goals:**

- 用一张规范化、owner-scoped 表保存四类结构化反馈，并提供稳定 upsert 键。
- 在服务端读取真实父记录完成 target ownership 与目标形状验证。
- 让 Chat/AIOps 使用同一 contracts、client、store 和可访问反馈控件。
- 重新打开业务目标时从服务器恢复；失败保留输入且不伪造成功。
- 通过统一错误和日志约束防止跨租户枚举及正文泄漏。

**Non-Goals:**

- 不支持 user message、session、diagnostic task、evidence、case 或任意自定义 target。
- 不汇总评分、训练模型、自动修改回答或执行纠正内容。
- 不把反馈保存到 localStorage，不增加匿名反馈或管理员跨 owner 查询。
- 不为多态目标伪造跨表数据库外键，也不改造现有父资源删除流程为级联删除。

## Decisions

### 1. 使用统一反馈表和归一化 subject key

Alembic 新增 `user_feedback`：`id`、`owner_user_id`、`target_type`、`target_id`、非空 `subject_key`、`rating`、可空 `reason/comment/correction`、`created_at/updated_at`。唯一约束为 `(owner_user_id, target_type, target_id, subject_key)`；无 subject 使用空串，使 SQLite 的唯一约束不会因 NULL 语义失效。Repository record 保持数据库形状，API mapper 将空串转换为 `subjectId: null`。

POST 使用该唯一键执行原子 upsert，更新时保留 id/createdAt。`positive|negative` 与固定 reason 目录提供稳定分析维度；comment 最大 2000 字符，correction 最大 4000 字符，trim 后空字符串写为 null。

备选方案是让 `subject_key` 可空并用应用层查重；SQLite 对多个 NULL 唯一值的处理会破坏预期，因此拒绝。拆成四张表会复制 owner、API 和 UI 逻辑，也拒绝。

### 2. 通过 resolver registry 验证真实目标

`FeedbackService` 依赖 Feedback Repository 与四类 target resolver；resolver 只暴露必要的 owner-scoped 读取，不把 ORM model 交给 service。

| targetType | targetId | subjectId | 服务端验证 |
| --- | --- | --- | --- |
| `chat_message` | assistant message id | `null` | owner-scoped 查询 message 且 role 为 assistant |
| `citation` | assistant message id | citation 的稳定 `chunkId` | owner-scoped 查询 assistant message，并在其 metadata references 中命中 chunkId |
| `diagnostic_step` | step id | `null` | owner-scoped 查询 diagnostic step |
| `diagnostic_report` | report id | `null` | owner-scoped 查询 diagnostic report |

Chat/diagnostic Repository 增加参数级 owner-scoped `get_message/get_step/get_report`，SQL 本身包含 owner 条件。resolver 不执行第二次无 scope 查询。不存在、已删除和跨 owner 全部映射为同一 `BUSINESS_RESOURCE_NOT_FOUND` 404；父资源直接不可见的语义与项目现有不可枚举规则一致。

GET 没有 subject query：`chat_message`、step、report 返回对应单一键记录；`citation` 在验证 assistant parent 后返回该消息下所有 citation subject，支持一次恢复引用列表。POST 对具体 subject 做完整验证。DELETE 只按当前 owner + feedback id 删除，即使多态父资源后来消失也不会扩大权限。

备选方案是客户端提交 owner 或只查询反馈表；前者可伪造，后者不能证明 target 属于当前用户，均拒绝。

### 3. 多态关联使用服务层完整性，不伪造数据库外键

四类目标位于不同表，且 citation 是 message metadata 中的稳定引用，不存在统一父表，因此 `user_feedback.target_id` 不设置虚假的跨表外键。GET/POST 每次先解析真实父目标；父资源删除后，反馈不再通过目标读取暴露，新的 upsert 也被拒绝。DELETE 仍允许 owner 按 feedback id 清理自己的孤立记录。

若未来需要物理清理，可在各领域删除事务旁增加显式清理，但本 change 不让 Chat/AIOps service 反向依赖反馈模块。

### 4. API 与 contracts 保持单一事实来源

`packages/api-contracts/src/feedback.ts` 定义 target/rating/reason 常量、DTO、查询、upsert body、列表和删除响应；manifest/OpenAPI 登记三条 bearer-protected operation。后端 Pydantic mirror 与合同测试证明枚举、字段可空性和 envelope 一致。

API 不包含 owner id：

- `GET /feedback?targetType&targetId`：验证目标后返回 `{items}`。
- `POST /feedback`：验证目标与 subject 后原子 upsert，返回保存后的 DTO。
- `DELETE /feedback/{id}`：owner-scoped 删除并返回 `{deleted: true, feedbackId}`。

路由复用 CurrentUser、统一 request id/envelope、401/403/404/validation error。服务和路由不记录 reason/comment/correction 值；必要日志只记录目标键、字段名和结果。

### 5. 前端以服务器状态和可重试草稿分层

新增 typed `feedbackClient`、protected Pinia `userFeedback` store 和 `UserFeedbackControl`。store 以 `targetType:targetId:subjectId` 索引已保存记录，并对相同 target group 的 GET 去重；组件维护编辑草稿。只有 POST/DELETE 成功响应才能更新 saved map，失败保留草稿、服务器旧值和明确错误。

Chat 只在 SSE complete 后历史对账拿到真实 assistant message id 时显示控件；回答使用 `chat_message + messageId + null`，citation 使用 `citation + messageId + chunkId`。每个新回合的 message id 隔离反馈。

AIOps 只给持久 `diagnostic_steps` 和 `diagnostic_report` 展示控件；plan/tool/evidence/status timeline item 不是反馈目标。重新打开会话/诊断时控件从 API 恢复。feedback store 注册到 protected store cleanup，登出清内存但不删除服务端数据。

备选方案是提交后立即乐观更新或将草稿写 localStorage；前者会伪造保存结果，后者违反服务器事实来源和认证清理边界，因此拒绝。

## Risks / Trade-offs

- [多态目标没有数据库外键，可能留下孤立反馈] → 所有读取/upsert 先解析父目标，孤立记录不可见；owner 仍可按反馈 id 删除，未来按容量需求增加领域删除清理。
- [citation id 来自 JSON metadata] → 只接受持久 assistant message references 中的稳定 `chunkId`，不接受客户端自造 subject。
- [多个 citation control 同时触发 GET] → store 按 target group 去重并缓存；重新进入业务页面可显式刷新。
- [固定 reason 目录以后可能扩展] → 由 shared contracts 统一扩展，禁止前后端私有字符串。
- [用户纠正内容可能敏感] → 长度限制、日志值黑名单、只对 owner 返回，不加入模型 prompt 或自动执行。

## Migration Plan

1. contracts 先增加反馈类型、operation 和测试。
2. Alembic 迁移创建 `user_feedback`、唯一约束和 owner/target 查询索引；upgrade head 验证 fresh database。
3. 增加 domain records/protocol、SQLite adapter、target resolvers、service、依赖注入与 FastAPI router。
4. 用后端验收测试覆盖四类 target、upsert/delete/恢复、父资源删除、跨租户、校验和日志脱敏。
5. 增加前端 client/store/control，接入 Chat/AIOps 并补组件与恢复测试。
6. 完整验证后同步 delta specs、归档；迁移回滚只删除本 change 新表，不修改父领域数据。

## Open Questions

无。P24 使用上述固定目标映射、reason 目录和文本上限；后续若新增 target type，必须通过新的 OpenSpec change 同时扩展 resolver、contracts 和 owner 测试。
