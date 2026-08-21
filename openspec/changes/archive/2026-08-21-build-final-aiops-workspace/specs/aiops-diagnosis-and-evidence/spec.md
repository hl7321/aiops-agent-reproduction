## MODIFIED Requirements

### Requirement: 诊断 API 暴露任务和完整证据链
系统 SHALL 提供 bearer-protected `POST /aiops/diagnostics`、`GET /aiops/diagnostics`、`GET /aiops/diagnostics/{id}`、`GET /aiops/diagnostics/{id}/evidence-chain` 与 `POST /aiops/diagnostics/{id}:stream`。创建输入 MUST 包含非空手工 query 或至少一条有界 ActiveAlert 快照，允许同时提供两者；当前合同不得增加独立 context 字段。列表按 updatedAt 与 id 确定性倒序；详情返回 task、backgroundJob、步骤和 nullable report；证据链返回规范化 evidence、report links 与 tool audits。所有响应使用共享 envelope/requestId 和 owner scope。

#### Scenario: 创建诊断
- **WHEN** 已认证用户提交合法的真实告警快照和可选 query，或提交非空手工 query 和空 alerts
- **THEN** API 返回统一 success envelope，其中包含 accepted task 和 queued backgroundJob，且不构造默认告警

#### Scenario: 通过手工 query 创建诊断
- **WHEN** 已认证用户提交非空 query 且未选择告警
- **THEN** API 使用同一 endpoint 创建 accepted task 和 queued backgroundJob，不构造默认告警

#### Scenario: 读取证据链
- **WHEN** owner 查询已产生证据的诊断
- **THEN** API 返回可按 step、tool call、report claim 和 evidence id 追溯的规范化链条

#### Scenario: 跨用户 API 访问
- **WHEN** 另一个用户请求 task 详情、证据链或 stream
- **THEN** API 使用与资源不存在相同的安全错误，不泄露任务状态或内容
