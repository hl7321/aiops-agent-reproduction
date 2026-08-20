## ADDED Requirements

### Requirement: 共享合同登记 Chat Prompt、Skill 与 configuration
共享合同 SHALL 定义 ChatPrompt、ChatSkill、ChatConfiguration、Prompt create/update、configuration update、删除结果与 Skill multipart policy。机器可读 OpenAPI 目录 MUST 登记 `GET/PUT /chat/configuration`、`POST /chat/prompts`、`PUT/DELETE /chat/prompts/{id}`、`POST /chat/skills`、`DELETE /chat/skills/{id}` 七个 operation；全部使用 `BearerAuth` 并复用 401/403/404，创建或上传按需登记 validation 与 `BUSINESS_CONFLICT` 409。

#### Scenario: 合同消费者读取 configuration DTO
- **WHEN** 前端或后端读取共享配置合同
- **THEN** 获得 prompts、skills、nullable selectedPromptId 与 selectedSkillIds 的稳定类型，以及 Prompt/Skill 的可编辑字段

#### Scenario: 合同消费者读取 Skill 上传 policy
- **WHEN** 客户端构建 Skill multipart 请求
- **THEN** 获得严格 filename `SKILL.md`、file 字段、256 KiB 限制、name/description 边界和规范化约束

#### Scenario: 合同消费者读取七个 operation
- **WHEN** 合同测试遍历机器可读 path 目录
- **THEN** 七个 operation 具有稳定 method、operationId、成功 DTO、BearerAuth 与共享错误列表

#### Scenario: 前端不复制配置 payload
- **WHEN** configuration client/store 发送选择或资产请求
- **THEN** 它直接消费共享 DTO 与 multipart policy，不定义另一套私有 Prompt/Skill payload
