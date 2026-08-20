## MODIFIED Requirements

### Requirement: SSE 使用共享判别联合
共享合同 SHALL 定义以 `type` 判别的 SSE 事件联合，事件公共字段 MUST 为 `id`、`type`、`channel`、`timestamp` 和单调递增的整数 `sequence`，其中 channel 仅允许 `chat` 或 `aiops`。事件目录 MUST 包含 `content.delta`、`reasoning.delta`、`tool.call`、`reference.source`、`task.status`、`report`、`complete` 和 `error`。

#### Scenario: 枚举全部 SSE 事件
- **WHEN** 合同测试遍历共享 SSE 事件目录
- **THEN** 八种 type 均存在且每种事件都携带公共字段与整数 sequence

#### Scenario: 表达工具调用生命周期
- **WHEN** SSE 发送 `tool.call` 事件
- **THEN** lifecycle 仅允许 `started`、`delta`、`completed` 或 `failed`，并携带稳定 toolCallId

#### Scenario: SSE 返回错误
- **WHEN** 流式处理需要发送 `error` 事件
- **THEN** 事件复用 HTTP failure envelope 中相同的 error 结构，不定义第二套错误 payload

## ADDED Requirements

### Requirement: 共享合同登记 Agent 流式聊天与工具审计
共享合同 SHALL 定义 ChatStreamMessageRequest、AgentToolCallAudit、审计状态与审计列表 data，并在机器可读 OpenAPI 目录登记 `POST /chat/sessions/{sessionId}/messages:stream` 和 `GET /chat/sessions/{sessionId}/tool-call-audits`。两个 path MUST 使用 `BearerAuth` 并复用 401/403；stream 还 MUST 登记 validation 与共享 SSE response。

#### Scenario: 合同消费者读取 stream path
- **WHEN** 合同测试读取流式消息 operation
- **THEN** 获得稳定 method、operationId、user content/metadata 请求、共享 SSE response、BearerAuth 和 401/403/validation 错误

#### Scenario: 合同消费者读取审计 DTO 与 path
- **WHEN** 合同测试读取会话工具审计 operation
- **THEN** 获得稳定 audit 字段、状态、父对象二选一语义、列表 data、BearerAuth 和 401/403

#### Scenario: 前端消费流式事件
- **WHEN** chat transport 收到跨网络 chunk 的流式消息事件
- **THEN** 它通过公共 SSE parser 与共享 event union 保留 id/sequence 并完成类型收窄，不复制私有事件联合
