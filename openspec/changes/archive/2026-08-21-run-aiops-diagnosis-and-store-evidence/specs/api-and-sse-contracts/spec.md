## ADDED Requirements

### Requirement: 共享合同登记 AIOps 诊断与证据链
共享 contracts SHALL 定义 DiagnosticTask、DiagnosticStep、DiagnosticEvidence、DiagnosticReport、ReportEvidenceLink、EvidenceChain、创建/列表/详情/stream 输入输出及 `accepted|running|succeeded|failed|cancelled` 诊断状态。机器可读 OpenAPI SHALL 登记 `POST /aiops/diagnostics`、`GET /aiops/diagnostics`、`GET /aiops/diagnostics/{id}`、`GET /aiops/diagnostics/{id}/evidence-chain` 与 `POST /aiops/diagnostics/{id}:stream`；全部使用 BearerAuth、共享 envelope/requestId、401/403/404，创建和 stream 按需登记 validation/system 错误。创建 data MUST 同时包含 diagnostic task 和 BackgroundJob。

#### Scenario: 合同消费者读取诊断 DTO
- **WHEN** TypeScript 或 Pydantic 消费诊断详情和证据链
- **THEN** 两端对状态、告警输入、步骤、证据、报告、provenance、nullable 字段和 backgroundJob 形状一致

#### Scenario: OpenAPI 登记五个诊断 path
- **WHEN** 合同测试遍历 AIOps diagnostic operations
- **THEN** 五个 path 具有稳定 method、operationId、成功数据、BearerAuth 和共享错误列表，且不存在诊断专用 cancel/retry path

### Requirement: SearchLog 缺失使用稳定系统错误
稳定错误目录 SHALL 增加 `SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE`，category 为 system、HTTP status 为 503，并提供不包含 MCP URL、connection、tool 列表或凭据的安全默认消息。Pydantic、TypeScript、background job failure 与 SSE error MUST 复用同一定义。

#### Scenario: 当前 owner 无日志工具
- **WHEN** 诊断发现当前 owner 没有可用 SearchLog 类工具
- **THEN** job 和 stream 使用稳定 code/category/status/message，且不生成报告或日志证据

## MODIFIED Requirements

### Requirement: SSE 使用共享判别联合
共享合同 SHALL 定义以 `type` 判别的 SSE 事件联合，事件公共字段 MUST 为 `id`、`type`、`channel`、`timestamp` 和单调递增的整数 `sequence`，其中 channel 仅允许 `chat` 或 `aiops`。事件目录 MUST 包含 `content.delta`、`reasoning.delta`、`tool.call`、`reference.source`、`task.status`、`report`、`complete` 和 `error`。`task.status` 的 lifecycle MUST 仅允许 `queued|running|succeeded|failed|cancelled`，并支持 nullable 中文 message 与 0..100 nullable progress；不得为计划、步骤或重规划增加新的 SSE type。

#### Scenario: 枚举全部 SSE 事件
- **WHEN** 合同测试遍历共享 SSE 事件目录
- **THEN** 八种 type 均存在且每种事件都携带公共字段与整数 sequence

#### Scenario: 表达工具调用生命周期
- **WHEN** SSE 发送 `tool.call` 事件
- **THEN** lifecycle 仅允许 `started`、`delta`、`completed` 或 `failed`，并携带稳定 toolCallId

#### Scenario: SSE 返回错误
- **WHEN** 流式处理需要发送 `error` 事件
- **THEN** 事件复用 HTTP failure envelope 中相同的 error 结构，不定义第二套错误 payload

#### Scenario: 表达 durable task 进度
- **WHEN** 后台诊断排队、执行、成功、失败或取消
- **THEN** task.status 使用对应 lifecycle、可访问 message 和有界 progress，不创建 plan/step/replan 事件
