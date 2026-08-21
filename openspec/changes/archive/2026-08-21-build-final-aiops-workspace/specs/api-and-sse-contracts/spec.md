## MODIFIED Requirements

### Requirement: 共享合同登记 AIOps 诊断与证据链
共享 contracts SHALL 定义 DiagnosticTask、DiagnosticStep、DiagnosticEvidence、DiagnosticReport、ReportEvidenceLink、EvidenceChain、创建/列表/详情/stream 输入输出及 `accepted|running|succeeded|failed|cancelled` 诊断状态。创建请求 MUST 保持 `query` 与有界 `alerts` 字段，并要求两者至少提供一项；未选择告警时可用非空 query 和空 alerts 创建手工诊断，不得增加独立 context 字段。机器可读 OpenAPI SHALL 登记 `POST /aiops/diagnostics`、`GET /aiops/diagnostics`、`GET /aiops/diagnostics/{id}`、`GET /aiops/diagnostics/{id}/evidence-chain` 与 `POST /aiops/diagnostics/{id}:stream`；全部使用 BearerAuth、共享 envelope/requestId、401/403/404，创建和 stream 按需登记 validation/system 错误。创建 data MUST 同时包含 diagnostic task 和 BackgroundJob。

#### Scenario: 合同消费者读取诊断 DTO
- **WHEN** TypeScript 或 Pydantic 消费诊断详情和证据链
- **THEN** 两端对状态、告警输入、步骤、证据、报告、provenance、nullable 字段和 backgroundJob 形状一致

#### Scenario: 手工 query 不选择告警
- **WHEN** 已认证用户提交非空 query 和空 alerts
- **THEN** 合同接受请求且不要求不存在的 context 字段

#### Scenario: 创建输入完全为空
- **WHEN** query 为空白且 alerts 为空
- **THEN** 合同返回共享 validation 错误且不创建诊断

#### Scenario: OpenAPI 登记五个诊断 path
- **WHEN** 合同测试遍历 AIOps diagnostic operations
- **THEN** 五个 path 具有稳定 method、operationId、成功数据、BearerAuth 和共享错误列表，且不存在诊断专用 cancel/retry path
