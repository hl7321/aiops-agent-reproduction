# Agent 工具调用审计规格

## Purpose

本能力为 Chat 与后续诊断任务提供 owner-scoped、生命周期完整且不会把敏感工具内容复制到运行日志的通用 Agent 工具调用审计边界。

## Requirements

### Requirement: 工具调用审计具有通用且排他的父对象
系统 SHALL 持久化工具审计的 owner、toolCallId、toolName、arguments、status、resultSummary、errorMessage、startedAt、completedAt 与 durationMs。每条审计 MUST 在 chatSessionId 与 diagnosticTaskId 中恰好选择一个父对象，且当前合同 MUST NOT 包含 parentCallId。

#### Scenario: Chat 工具调用开始
- **WHEN** Chat Agent 即将执行一个工具
- **THEN** 系统创建 owner-scoped、status 为 started 且 chatSessionId 非空的审计记录

#### Scenario: 父对象无效
- **WHEN** 审计记录同时提供两个父对象或两个父对象均为空
- **THEN** 持久化边界拒绝该记录

### Requirement: 审计记录覆盖工具完整生命周期
系统 SHALL 在工具开始前记录 started，并在成功或失败后更新同一 toolCallId 的审计。成功记录 MUST 包含有界 resultSummary、completedAt 与 durationMs；失败记录 MUST 包含脱敏 errorMessage、completedAt 与 durationMs。

#### Scenario: 工具成功
- **WHEN** 已开始的工具正常返回
- **THEN** 同一审计更新为 completed，并保存有界摘要和非负 durationMs

#### Scenario: 工具失败
- **WHEN** 已开始的工具抛出异常
- **THEN** 同一审计更新为 failed，错误文本经过安全脱敏且生命周期时间完整

### Requirement: 工具审计查询强制 owner scope
系统 SHALL 提供 `GET /chat/sessions/{id}/tool-call-audits`，先按当前 owner 验证父会话，再按 owner 与 session 查询并以 startedAt、id 稳定排序。父会话不存在或跨用户 MUST 返回相同 `AUTH_FORBIDDEN` 403。

#### Scenario: owner 查询会话审计
- **WHEN** 当前 owner 查询自己的会话审计
- **THEN** 系统返回该会话内按稳定顺序排列的审计，不包含其他会话或用户记录

#### Scenario: 跨用户查询审计
- **WHEN** 用户 B 查询用户 A 会话的工具审计
- **THEN** 系统返回 `AUTH_FORBIDDEN` 403，且不泄漏会话或审计字段

### Requirement: 审计数据与运行日志使用不同披露边界
arguments SHALL 作为 owner-scoped 审计数据保存并仅向同一 owner 返回；结构化运行日志 MUST NOT 记录 prompt、query、参数值、完整 arguments、工具输出、token、消息正文或 reasoning，只能记录必要标识、状态、duration 与参数键名。

#### Scenario: 工具参数包含 sentinel secret
- **WHEN** 工具 arguments 的某个值包含敏感 sentinel
- **THEN** owner-scoped 审计可按合同保存参数，但捕获的应用日志不包含 sentinel、query 或工具输出

#### Scenario: provider 错误包含 API key
- **WHEN** 工具或 provider 异常文本包含当前 API key
- **THEN** 审计 errorMessage、SSE error 与日志均以 `[redacted]` 替换该 key

### Requirement: MCP 工具审计只持久化最小安全信息
MCP tool 调用 SHALL 复用通用 owner-scoped 工具审计生命周期，但其 arguments 持久化形状 MUST 只表达参数键已提供，不得保存参数值、URL query、完整工具输出或凭据。审计 SHALL 保留 toolName、status、started/completedAt、durationMs、参数键和有界安全 resultSummary/errorMessage；结构化日志使用相同或更严格的披露边界。

#### Scenario: MCP 参数含 sentinel secret
- **WHEN** 模型调用 MCP tool 且某个参数值包含 sentinel secret
- **THEN** 审计与日志可包含该参数键，但不包含 sentinel、完整 arguments 或工具输出

#### Scenario: MCP 调用失败
- **WHEN** MCP tool 返回包含 URL query 或凭据的异常
- **THEN** 审计 errorMessage、SSE error 和日志都只包含脱敏安全错误，并保留 failed 与 durationMs
