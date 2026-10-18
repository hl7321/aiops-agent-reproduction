# Spec Delta

## ADDED Requirements

### Requirement: 报告生成失败使用独立稳定错误码

稳定错误目录 SHALL 增加 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`，category 为 system、HTTP status 为 200，并提供不包含 prompt、模型输出、证据正文或凭据的安全默认消息。Pydantic、TypeScript、background job failure 与前端展示 MUST 复用同一定义；该错误码 MUST 只用于"本轮证据评估为 `verified_evidence`、但报告模型调用或结构校验失败"的情况。

#### Scenario: 证据充分但报告生成失败

- **WHEN** 诊断已拿到真实日志命中，但报告模型调用或结构校验失败并生成兜底报告
- **THEN** 任务 `failureCode` 为 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`，报告信任状态仍为 `insufficient_evidence`

#### Scenario: 证据确实不足

- **WHEN** 本轮没有任何真实日志命中，报告按既有规则表达证据不足
- **THEN** 任务继续使用 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`，不得改用报告生成失败错误码

#### Scenario: 两种报告失败在契约两端一致

- **WHEN** 后端与 TypeScript 消费同一份稳定错误目录
- **THEN** 两端对 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED` 的 code、category、httpStatus 与安全默认消息取值一致
