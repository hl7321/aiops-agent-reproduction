## Why

Chat 与 AIOps 已有稳定、owner-scoped 的持久目标，但用户仍无法对回答、引用、诊断步骤和报告留下可恢复反馈。现在需要建立统一反馈边界，既支持产品页面编辑/恢复，也确保任意 target ownership 都由服务端依据真实父记录验证。

## What Changes

- 新增 `user_feedback` Alembic schema、不可变 record、Repository Protocol/SQLite adapter 与 owner-scoped service。
- 新增四类固定目标：assistant `chat_message`、单条 `citation`、`diagnostic_step`、`diagnostic_report`；服务端 resolver 读取真实父记录验证 owner 与 citation subject。
- 新增 `GET /feedback?targetType&targetId`、upsert `POST /feedback` 和 `DELETE /feedback/{id}`，全部复用统一 envelope、requestId、认证和不可枚举错误。
- 统一 `positive|negative` rating 与问题类型目录；对 reason/comment/correction 执行 trim、长度和目标形状校验，不记录反馈正文日志。
- 新增 typed feedback client/store 和可复用 `UserFeedbackControl`，接入 Chat assistant message/citation 与 AIOps step/report；重新打开目标时从服务器恢复，失败时保留草稿且不乐观伪造成功。
- 不为 user message、整场会话、diagnostic task、evidence 或 case 增加反馈目标；不把反馈写入 localStorage，也不信任客户端提供的 owner 信息。

## Capabilities

### New Capabilities

- `user-feedback-collection`: 结构化反馈的数据模型、target ownership、API、恢复语义、前端控件与安全约束。

### Modified Capabilities

- `api-and-sse-contracts`: 登记 Feedback DTO、允许集合与三条 bearer-protected OpenAPI operation。
- `final-chat-workspace-and-citations`: assistant answer 和单条 citation 增加可恢复反馈交互。
- `final-aiops-workspace`: diagnostic step 和 report 增加可恢复反馈交互。

## Impact

影响后端 Alembic、`super_ai.feedback`、SQLite extended adapter、应用依赖注入与路由，影响 `packages/api-contracts` 的 typed contract/manifest/OpenAPI，以及前端 feedback client/store/control 与 Chat/AIOps 页面测试。无新外部依赖、无模型或基础设施调用、无 import-time I/O。
