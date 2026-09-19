## MODIFIED Requirements

### Requirement: 共享合同登记 AIOps 诊断与证据链

共享 contracts SHALL 定义 DiagnosticTask、DiagnosticStep、DiagnosticEvidence、DiagnosticReport、ReportEvidenceLink、EvidenceChain、创建/列表/详情/stream 输入输出及 `accepted|running|succeeded|failed|cancelled` 诊断状态。创建请求 MUST 保持 `query` 与有界 `alerts` 字段，并要求两者至少提供一项；未选择告警时可用非空 query 和空 alerts 创建手工诊断，不得增加独立 context 字段。机器可读 OpenAPI SHALL 登记 `POST /aiops/diagnostics`、`GET /aiops/diagnostics`、`GET /aiops/diagnostics/{id}`、`GET /aiops/diagnostics/{id}/evidence-chain` 与 `POST /aiops/diagnostics/{id}:stream`；全部使用 BearerAuth、共享 envelope/requestId、401/403/404，创建和 stream 按需登记 validation/system 错误。创建 data MUST 同时包含 diagnostic task 和 BackgroundJob。

**诊断终态 MUST 表达报告可信度，而不是"报告已生成"。** 契约 MUST 使客户端能区分以下三种收尾：

- 报告信任状态为 `verified_evidence` → 任务 `succeeded`。
- 报告信任状态为 `insufficient_evidence` → 任务 MUST NOT 为 `succeeded`；MUST 以共享错误目录中表达"证据不足、无法给出可信结论"的稳定错误码收尾，使任务落到 `failed` 且 `failureCode` 可区分于系统故障。
- 报告信任状态为 `execution_failed` → 任务 `failed`。

该"证据不足"错误码 MUST 与其他 AIOps 系统错误一样进入共享错误目录，声明唯一 code、category、HTTP status 与不含内部细节的安全默认消息；契约两端的状态与错误码枚举 MUST 保持一致，前端据此把"诊断成功"与"未能得出结论"展示为不同结果。

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

#### Scenario: 证据不足的诊断不被当作成功

- **WHEN** 诊断生成了报告但报告信任状态为 insufficient_evidence
- **THEN** 任务终态不是 succeeded，`failureCode` 为该稳定错误码，且报告中仍保留已收集到的真实证据链

#### Scenario: 两种失败可区分

- **WHEN** 客户端读取一个 failed 诊断
- **THEN** 它能凭 `failureCode` 区分"系统执行失败"与"证据不足未能得出结论"，两者不共用同一个 code
