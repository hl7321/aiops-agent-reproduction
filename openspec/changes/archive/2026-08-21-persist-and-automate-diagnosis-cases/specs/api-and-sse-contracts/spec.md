## ADDED Requirements

### Requirement: 共享合同登记诊断 case 查询
共享 contracts SHALL 定义 DiagnosticCase、列表与详情 data，并在机器可读 OpenAPI 登记 bearer-protected `GET /aiops/diagnostic-cases` 与 `GET /aiops/diagnostic-cases/{id}`；两条操作 MUST 复用共享 envelope/requestId、401/403/404。

#### Scenario: 合同消费者读取 case
- **WHEN** TypeScript 或 Pydantic 消费 case 列表与详情
- **THEN** owner/task/report/document/index task、结构化字段、keywords/evidenceIds 与时间字段形状一致

### Requirement: 共享合同登记 legacy 手动知识保存
共享 contracts SHALL 登记 bearer-protected `POST /aiops/diagnostics/{id}:save-to-knowledge`，成功 data 包含 KnowledgeDocument 与 DocumentIndexTask，并复用 401/403/404、validation 与 BUSINESS_CONFLICT；不得声明该操作创建 structured case。

#### Scenario: 合同消费者调用手动保存
- **WHEN** 前端或测试读取 legacy operation
- **THEN** 获得稳定 method、operationId、成功 DTO、安全方案和共享错误目录
