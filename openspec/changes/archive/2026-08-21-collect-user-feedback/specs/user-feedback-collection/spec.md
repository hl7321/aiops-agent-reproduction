## Purpose

定义 owner-scoped 结构化用户反馈的持久化、目标归属验证、恢复和前端交互边界，使 Chat 与 AIOps 的真实持久目标能够被安全评价、修改和删除。

## ADDED Requirements

### Requirement: 反馈数据使用稳定键和有界结构

系统 SHALL 使用 `owner_user_id + target_type + target_id + subject_key` 作为反馈唯一键，其中数据库 `subject_key` 永不为空；无 subject 的目标 SHALL 将其归一化为空串，并在 DTO 中暴露为 `subjectId: null`。`targetType` SHALL 仅允许 `chat_message`、`citation`、`diagnostic_step`、`diagnostic_report`，`rating` SHALL 仅允许 `positive`、`negative`；可选问题类型 `reason` SHALL 仅允许 `incorrect`、`incomplete`、`irrelevant`、`unclear`、`unsafe`、`other`。系统 SHALL trim 文本，将空白文本归一化为 `null`，并将 `comment` 限制为最多 2000 个字符、`correction` 限制为最多 4000 个字符。

#### Scenario: 无 subject 反馈归一化

- **WHEN** 当前用户为 assistant message 提交不含 `subjectId` 的反馈
- **THEN** 数据库保存空串 `subject_key`
- **AND** API 返回同一反馈时 `subjectId` 为 `null`

#### Scenario: 相同反馈键执行 upsert

- **WHEN** 当前用户再次提交相同 `targetType + targetId + subjectId` 的反馈
- **THEN** 系统更新原记录并保持原 `id` 与 `createdAt`
- **AND** 不创建第二条违反唯一键的记录

#### Scenario: 输入被规范化和限制

- **WHEN** 用户提交带首尾空白的 comment/correction 或不在允许集合内的 targetType/rating/reason
- **THEN** 合法文本被 trim，纯空白值成为 `null`
- **AND** 非法枚举或超过长度上限的输入返回统一验证错误

### Requirement: 服务端验证四类真实目标的 owner 与形状

系统 SHALL 在读取或写入反馈前，根据当前认证用户通过 owner-scoped Repository 查询真实父记录，不得接受客户端 owner id，也不得通过无 scope 查询判断跨用户目标是否存在。映射 SHALL 固定为：`chat_message` 的 `targetId` 是 assistant message id 且无 subject；`citation` 的 `targetId` 是 assistant message id、`subjectId` 是该消息 metadata references 中的稳定 citation/chunk id；`diagnostic_step` 的 `targetId` 是 step id 且无 subject；`diagnostic_report` 的 `targetId` 是 report id 且无 subject。

#### Scenario: assistant message 目标通过验证

- **WHEN** 当前用户对自己会话中的 assistant message 提交无 subject 的反馈
- **THEN** 服务端通过 owner-scoped message 查询验证其 role 与归属
- **AND** 接受该反馈

#### Scenario: citation subject 必须来自对应消息

- **WHEN** 当前用户提交 citation 反馈
- **THEN** 服务端先读取自己的 assistant message
- **AND** 仅当 `subjectId` 命中该消息 metadata references 中的稳定 citation/chunk id 时接受

#### Scenario: 诊断目标通过真实父记录验证

- **WHEN** 当前用户对 diagnostic step 或 diagnostic report 提交反馈
- **THEN** 服务端分别使用 owner-scoped step/report 查询验证归属
- **AND** 拒绝错误的 subject 形状

#### Scenario: 不存在与跨用户不可枚举

- **WHEN** 目标不存在、父记录已经删除或目标属于其他用户
- **THEN** 读取和 upsert 返回同一不可枚举的 `BUSINESS_RESOURCE_NOT_FOUND` 404
- **AND** 响应不泄漏另一个用户或目标的细节

### Requirement: 反馈 API 支持恢复、upsert 和 owner-scoped 删除

系统 SHALL 提供认证 API：`GET /feedback?targetType&targetId`、`POST /feedback` 与 `DELETE /feedback/{id}`。GET SHALL 先验证目标归属，再返回当前 owner 对该目标类型和 target id 的反馈；citation GET SHALL 一次返回该 assistant message 下各 subject 的反馈。POST SHALL 只在目标验证通过后执行原子 upsert。DELETE SHALL 仅凭当前 owner 与 feedback id 删除，未知或其他 owner 的 id 使用不可枚举 404。所有响应 SHALL 使用共享 envelope、request id 和错误目录。

#### Scenario: 重新打开目标恢复反馈

- **WHEN** 当前用户重新读取自己的 assistant message、citations、diagnostic step 或 report 的反馈
- **THEN** GET 返回服务器持久化的最新记录
- **AND** 不依赖浏览器 localStorage 或内存中的旧页面状态

#### Scenario: 删除自己的反馈

- **WHEN** 当前用户删除自己的一条反馈
- **THEN** 系统删除该记录并返回明确 deleted 结果
- **AND** 后续读取不再返回该记录

#### Scenario: 不能删除其他用户反馈

- **WHEN** 当前用户使用其他用户的 feedback id 调用删除
- **THEN** 系统返回与未知 feedback id 相同的不可枚举 404

### Requirement: 反馈正文不得进入运行日志

系统 SHALL 将 reason、comment、correction 视为敏感用户正文；结构化日志最多记录 request id、目标类型、目标 id、字段名和操作结果，不得记录这些字段的值。

#### Scenario: 日志不包含 sentinel 正文

- **WHEN** 用户提交包含唯一 sentinel 的 comment 和 correction，且请求成功或失败
- **THEN** 捕获的应用日志不包含该 sentinel

### Requirement: 前端提供可恢复且诚实的反馈控件

前端 SHALL 提供可复用 `UserFeedbackControl`，支持赞同/反对、问题类型、评论、纠正、更新和删除；Chat assistant answer/citation 与 AIOps diagnostic step/report SHALL 使用同一 typed client/store。控件 SHALL 从服务器恢复已保存值，不得把领域反馈写入 localStorage；提交或删除只有收到成功响应后才能改变已保存状态，失败 SHALL 保留用户草稿和可重试错误。

#### Scenario: 提交失败保留草稿

- **WHEN** 用户填写反馈而 POST 失败
- **THEN** 控件保留 rating、reason、comment、correction 输入
- **AND** 不把它显示为已保存成功

#### Scenario: 删除失败保留服务器状态

- **WHEN** 用户删除反馈而 DELETE 失败
- **THEN** 已保存反馈仍显示在控件中
- **AND** 用户可以重试

#### Scenario: 受保护数据清理

- **WHEN** 用户登出或认证失效触发 protected store 清理
- **THEN** feedback store 清空反馈缓存与请求状态
- **AND** 不删除服务端持久反馈
