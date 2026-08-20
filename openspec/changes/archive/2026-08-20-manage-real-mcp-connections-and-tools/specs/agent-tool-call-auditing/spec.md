## ADDED Requirements

### Requirement: MCP 工具审计只持久化最小安全信息
MCP tool 调用 SHALL 复用通用 owner-scoped 工具审计生命周期，但其 arguments 持久化形状 MUST 只表达参数键已提供，不得保存参数值、URL query、完整工具输出或凭据。审计 SHALL 保留 toolName、status、started/completedAt、durationMs、参数键和有界安全 resultSummary/errorMessage；结构化日志使用相同或更严格的披露边界。

#### Scenario: MCP 参数含 sentinel secret
- **WHEN** 模型调用 MCP tool 且某个参数值包含 sentinel secret
- **THEN** 审计与日志可包含该参数键，但不包含 sentinel、完整 arguments 或工具输出

#### Scenario: MCP 调用失败
- **WHEN** MCP tool 返回包含 URL query 或凭据的异常
- **THEN** 审计 errorMessage、SSE error 和日志都只包含脱敏安全错误，并保留 failed 与 durationMs
