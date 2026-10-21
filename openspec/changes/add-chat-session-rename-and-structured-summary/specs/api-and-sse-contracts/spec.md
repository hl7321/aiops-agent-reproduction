# Spec Delta

## ADDED Requirements

### Requirement: 共享合同登记会话重命名

共享 contracts SHALL 定义 `UpdateChatSessionTitleRequest { title: string }`，并在机器可读 OpenAPI 登记 bearer-protected `PATCH /chat/sessions/{id}`，成功返回 `ChatSessionDetailData`；操作 MUST 复用共享 envelope/requestId、`AUTH_REQUIRED` 401、`AUTH_FORBIDDEN` 403、`BUSINESS_RESOURCE_NOT_FOUND` 404 与 `VALIDATION_REQUEST_INVALID` 422。Pydantic、TypeScript 与 manifest MUST 保持一致。

#### Scenario: 合同消费者读取重命名请求

- **WHEN** TypeScript 或 Pydantic 消费会话重命名请求与响应
- **THEN** 两端对 `title`、成功 data、错误码与 requestId 形状一致

#### Scenario: OpenAPI 登记重命名 path

- **WHEN** 合同测试遍历 Chat session operations
- **THEN** `PATCH /chat/sessions/{id}` 具有 BearerAuth、成功数据与 401/403/404/422 错误列表
