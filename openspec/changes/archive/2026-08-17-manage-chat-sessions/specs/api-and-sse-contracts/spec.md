## ADDED Requirements

### Requirement: 共享合同登记聊天会话与消息生命周期
共享合同 SHALL 定义 ChatSession、ChatMessage、ChatMessageMetadata、ChatReference、会话列表/详情、创建、追加、清空和删除的数据类型。message role MUST 限定为 `user|assistant|system|tool`，metadata MUST 允许保存 references 与 toolCallIds；删除成功数据 MUST 为 `{deleted:true,sessionId}`。

机器可读 OpenAPI 目录 MUST 登记 `POST /chat/sessions`、`GET /chat/sessions`、`GET /chat/sessions/{id}`、`POST /chat/sessions/{id}/messages`、`POST /chat/sessions/{id}/messages:clear` 和 `DELETE /chat/sessions/{id}`。所有路径 MUST 使用 `BearerAuth` 并复用 `AUTH_REQUIRED` 401 与 `AUTH_FORBIDDEN` 403；追加消息还 MUST 登记验证失败响应。

#### Scenario: 合同消费者读取聊天 DTO
- **WHEN** 前端或后端合同测试读取聊天类型
- **THEN** 获得稳定的会话、消息、role、metadata、reference、列表、详情、清空和删除数据形状

#### Scenario: 合同消费者读取聊天 path
- **WHEN** 合同测试遍历机器可读 OpenAPI path 目录
- **THEN** 六种聊天操作具有稳定 method、operationId、成功数据类型、BearerAuth 和共享 401/403 错误

#### Scenario: 追加消息验证失败
- **WHEN** 消息 role、content 或 metadata 不满足共享合同
- **THEN** 后端返回统一 validation error envelope，且序列化形状与共享合同一致

#### Scenario: 前后端禁止私有聊天 payload
- **WHEN** 仓库合同测试扫描聊天 transport、store 与后端响应模型
- **THEN** 它们直接消费共享聊天合同或由跨语言合同测试证明一致，不存在另一套临时会话或消息结构
