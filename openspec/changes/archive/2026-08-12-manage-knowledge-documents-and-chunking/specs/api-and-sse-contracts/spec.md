## ADDED Requirements

### Requirement: 共享合同登记知识文档上传与管理边界
共享合同 SHALL 定义 KnowledgeBase、KnowledgeDocument、ChunkingConfig、ChunkPreview DTO，以及 10 MiB、`.md/.pdf`、MIME、multipart 字段等上传 policy 常量。机器可读 OpenAPI 目录 MUST 登记知识库列表、文档列表/上传/详情/删除/预览六种操作；受保护 path MUST 使用 `BearerAuth` 并复用 401/403/404，上传额外登记 validation 与 `BUSINESS_CONFLICT` 409。

#### Scenario: 合同消费者读取上传 policy
- **WHEN** 前端或测试读取共享 policy
- **THEN** 获得精确最大字节数、扩展名/MIME 映射、multipart file/config/overwrite 字段和三种策略名

#### Scenario: 合同消费者读取知识 path
- **WHEN** 遍历机器可读 path 目录
- **THEN** 六种操作具有稳定 method、operationId、成功 DTO、安全方案与错误列表
