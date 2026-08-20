## ADDED Requirements

### Requirement: 共享合同登记 MCP 连接与检查边界
共享 contracts SHALL 定义 McpConnection、McpDiscoveredTool、McpConnectionCheckResult、create/update/delete 数据、`sse|streamable_http` transport 与 `connected|failed` check 状态。机器可读 OpenAPI 目录 MUST 登记 `GET/POST /mcp/connections`、`PUT/DELETE /mcp/connections/{id}` 与 `POST /mcp/connections/{id}:check` 五个 operation；全部使用 BearerAuth 并复用 401/403，create/update 声明 validation/conflict，check 声明安全 MCP 系统错误。TypeScript、Pydantic、manifest 和前端 transport MUST 对字段、nullable 语义与错误目录保持一致。

#### Scenario: 合同消费者读取 MCP DTO
- **WHEN** 前端或后端合同测试构造带最近检查和发现 tools 的连接
- **THEN** transport、URL、范围字段、nullable 状态与 tool 快照形状在跨语言实现中一致

#### Scenario: 五个 MCP operations 受保护
- **WHEN** 合同测试遍历 MCP path 目录
- **THEN** 每个 operation 具有稳定 method、operationId、成功 DTO、BearerAuth 和对应共享错误

#### Scenario: MCP 失败使用稳定错误
- **WHEN** Chat 装配因连接失败或 tool 同名冲突而终止
- **THEN** HTTP/SSE 使用共享目录中的安全 code、category、httpStatus 与 message，不自造私有 MCP error payload
