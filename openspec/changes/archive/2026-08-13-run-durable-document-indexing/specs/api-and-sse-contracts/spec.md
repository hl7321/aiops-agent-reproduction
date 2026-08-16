## ADDED Requirements

### Requirement: 共享合同登记 durable 文档索引任务
共享合同 SHALL 定义 DocumentIndexTask DTO、`pending|running|succeeded|failed|cancelled` 状态联合、failureReason/retryOfTaskId 可选字段，以及创建任务、读取详情和 retry 三种受保护操作。机器可读 OpenAPI 目录 MUST 使用 bearer、统一 envelope/requestId，并复用 401/403/404/validation 错误；retry 返回新的任务 DTO。

#### Scenario: 合同消费者读取索引状态
- **WHEN** 前端或后端读取共享索引任务合同
- **THEN** 获得精确五种领域状态，且 queued 不是公开领域状态

#### Scenario: 合同消费者读取索引操作
- **WHEN** 遍历机器可读 path 目录
- **THEN** 创建、详情和 retry 具有稳定 method、operationId、成功 DTO、安全方案与错误列表

#### Scenario: API 返回 UI-ready 任务
- **WHEN** owner 创建、查询或重试索引任务
- **THEN** 成功 envelope 的 data 包含 task、document、KB、状态、failureReason、retryOfTaskId 和时间戳，且不包含 jobId
