## ADDED Requirements

### Requirement: 共享合同登记活跃告警输入
共享 contracts SHALL 定义 `prometheus-v1|alertmanager-v2` source type、`pending|firing|suppressed|unprocessed` alert status、AlertSource、ActiveAlert 与 ActiveAlertsData。ActiveAlert MUST 包含 alertName、nullable service/severity、status、startsAt、labels、annotations、source 和 rawContext。机器可读 OpenAPI SHALL 登记 bearer-protected `GET /aiops/alerts/active`，成功数据为 ActiveAlertsData，并复用 AUTH_REQUIRED 401、AUTH_FORBIDDEN 403 与 SYSTEM_ALERT_SOURCES_UNAVAILABLE 503；不得定义 provider 状态集合。

#### Scenario: 合同消费者读取告警 DTO
- **WHEN** TypeScript 或 Pydantic 消费包含 source/status/rawContext 的标准告警
- **THEN** 两端对字段名、nullable 语义、枚举和 envelope 形状保持一致

#### Scenario: OpenAPI 登记认证告警 path
- **WHEN** 合同测试检查 `/aiops/alerts/active`
- **THEN** path 使用 GET、稳定 operationId、BearerAuth、ActiveAlertsData 和共享 401/403/503 错误

### Requirement: 告警全源不可用使用稳定错误
稳定错误目录 SHALL 增加 `SYSTEM_ALERT_SOURCES_UNAVAILABLE`，category 为 system、HTTP status 为 503，并提供不包含 source URL、Basic Auth、响应正文或 CLS 凭据的安全默认消息。Pydantic、TypeScript 和 FastAPI failure envelope MUST 复用同一定义。

#### Scenario: 全源请求失败
- **WHEN** aggregator 报告没有任何成功 source
- **THEN** API 返回 code、system category、503、安全 message 与 requestId，不返回私有错误 payload
