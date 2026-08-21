## ADDED Requirements

### Requirement: 共享合同登记结构化反馈 API

`packages/api-contracts` SHALL 成为 Feedback target/rating/reason 允许集合、DTO、查询、upsert、删除响应与 OpenAPI operation 的单一事实来源。`UserFeedback.subjectId` SHALL 为可空字段，并与数据库空串 `subject_key` 的 API 映射一致；三条 operation SHALL 声明 bearer、统一 envelope、401、403、404 和验证错误。

#### Scenario: 合同包含三条反馈 operation

- **WHEN** contracts manifest/OpenAPI 被生成和检查
- **THEN** 它包含 `GET /feedback`、`POST /feedback`、`DELETE /feedback/{id}`
- **AND** operation 复用共享认证、envelope 与错误结构

#### Scenario: 前后端使用同一允许集合

- **WHEN** 前端 client 和后端 Pydantic contract 处理反馈
- **THEN** targetType、rating、reason 与 shared TypeScript contract 的值集合一致
- **AND** 未提供 subject 的 DTO 使用 `null` 而不是空串
