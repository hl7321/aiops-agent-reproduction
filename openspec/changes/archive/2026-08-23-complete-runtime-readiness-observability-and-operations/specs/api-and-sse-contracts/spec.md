## ADDED Requirements

### Requirement: 共享合同登记运行时交付探针
共享合同 SHALL 定义 RuntimeDependencyResult、ReadinessStatus、ConfigurationCheck、ProcessMetrics 等 DTO，并在机器可读 OpenAPI 目录登记 `GET /ready`、`GET /config/check`、`GET /health/mcp` 与 `GET /metrics`。这些公开诊断 path SHALL 使用统一 envelope 与 request ID，但不要求 bearer；503 响应 MUST 使用共享 `SYSTEM_UNAVAILABLE` 语义并保留安全 typed details。

#### Scenario: 合同消费者读取运行时探针
- **WHEN** contracts 或后端合同测试遍历机器可读 path 目录
- **THEN** 四个 path 具有稳定 operationId、成功 DTO、统一 503 错误与无 bearer 的公开诊断语义

#### Scenario: 前后端序列化部分不可用
- **WHEN** readiness 或 config check 包含一个 unavailable 依赖
- **THEN** TypeScript 与 Pydantic 形状对齐 status、latencyMs、safe error 和 overall 503 语义
