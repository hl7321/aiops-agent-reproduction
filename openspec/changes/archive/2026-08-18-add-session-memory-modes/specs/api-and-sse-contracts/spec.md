## ADDED Requirements

### Requirement: 共享合同定义会话记忆 DTO 与操作
共享 contracts SHALL 定义 `every_30_turns|context_70_percent|manual` 记忆模式、Chat session 的记忆字段、更新模式请求，以及 `PUT /chat/sessions/{id}/memory` 和 `POST /chat/sessions/{id}/memory:compact` 两条 bearer-protected OpenAPI operation。后端 Pydantic 序列化、前端 TypeScript 类型和机器可读 manifest MUST 保持一致。

#### Scenario: 合同读取会话记忆
- **WHEN** contracts 测试构造带完整记忆字段的 ChatSession
- **THEN** TypeScript、Pydantic 与 manifest 对字段名称、nullable 语义和模式目录一致

#### Scenario: 两条记忆操作受保护
- **WHEN** 检查机器可读 OpenAPI operation
- **THEN** 两条 path 使用 bearer 并声明共享 401、403、validation 与安全系统错误

### Requirement: 上下文上限使用稳定 HTTP 与 SSE 错误
稳定错误目录 SHALL 增加 `CHAT_CONTEXT_LIMIT_REACHED`，category 为 `business`、HTTP status 为 409，并提供不包含 prompt、消息、摘要或模型凭据的安全默认消息。HTTP failure envelope 与 SSE `error` MUST 复用相同 `ApiErrorModel` 字段，不能复制私有错误 payload。

#### Scenario: HTTP 上下文拒绝
- **WHEN** 流式 endpoint 在响应开始前拒绝达到 95% 的候选消息
- **THEN** failure envelope 返回 code、business category、409、安全 message 和 requestId

#### Scenario: SSE 上下文错误
- **WHEN** 已开始的流必须用上下文上限错误终止
- **THEN** `error` event 的 error 对象与目录中的 code、category、httpStatus 和默认消息一致

### Requirement: 模型 capability 缺失使用稳定配置错误
稳定错误目录 SHALL 增加 `SYSTEM_MODEL_CAPABILITY_MISSING`，用于当前 chat model 缺失有效 `contextWindowTokens` 的情况。错误 MUST 在创建模型 client 前产生并保持凭据脱敏，HTTP 与 SSE MUST 复用同一结构。

#### Scenario: 会话预算无法取得窗口
- **WHEN** 当前模型没有 capability profile
- **THEN** API 返回 `SYSTEM_MODEL_CAPABILITY_MISSING` 的安全系统错误，不使用猜测窗口继续执行
