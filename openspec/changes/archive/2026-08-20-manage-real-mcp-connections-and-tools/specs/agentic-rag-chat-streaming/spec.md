## ADDED Requirements

### Requirement: Chat Agent 按请求装配真实 MCP tools
每轮 Chat Agent SHALL 在 owner 会话、记忆预算与配置快照通过后，从共享 MCP 连接来源为当前 CurrentUser 发现请求级 MCP tools，并与 `knowledge_retrieval`、`get_current_time` 和当前 `load_skill` 同时交给 `create_agent` 自主选择。系统 MUST NOT 在模型选择前调用 MCP tool，MCP 发现失败或工具同名冲突 MUST 使本轮显式失败，不得用假结果、静态 catalog 或随机工具掩盖。

#### Scenario: 模型不调用 MCP tool
- **WHEN** 本轮已注入真实 MCP tools 但模型判断无需调用
- **THEN** 系统不执行任何 MCP tool，不发送虚假 `tool.call` 或审计

#### Scenario: 模型调用真实 MCP tool
- **WHEN** 模型选择一个当前 owner 来源中的 MCP tool
- **THEN** 真实调用产生共享 started/completed 或 started/failed `tool.call` 事件和同一 toolCallId 的 owner-scoped 审计

#### Scenario: MCP 装配失败
- **WHEN** enabled MCP Server 无法在有界重试内完成发现
- **THEN** 本轮返回共享安全错误，不调用模型、不保存半条 assistant 消息且不生成假回答
