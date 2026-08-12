## ADDED Requirements

### Requirement: 共享合同登记后台任务管理边界
共享合同 SHALL 定义 BackgroundJob、BackgroundJobEvent、任务状态与取消/重试响应类型，并在机器可读 OpenAPI 目录登记 `GET /background-jobs`、`GET /background-jobs/{id}`、`POST /background-jobs/{id}:cancel` 和 `POST /background-jobs/{id}:retry`。四个 path MUST 使用 `BearerAuth` 并复用 `AUTH_REQUIRED`、`AUTH_FORBIDDEN` 与 `BUSINESS_RESOURCE_NOT_FOUND`。

#### Scenario: 合同消费者读取后台任务 path
- **WHEN** 前端或合同测试遍历共享 path 目录
- **THEN** 四个后台任务 path 具有稳定 method、operationId、成功数据类型、安全方案和错误列表

#### Scenario: 前后端序列化任务
- **WHEN** 后端返回任务详情或事件
- **THEN** Pydantic JSON 形状与 TypeScript 共享 DTO 一致且不包含 heartbeatAt 或 result
