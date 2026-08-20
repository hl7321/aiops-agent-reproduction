## Why

当前 Chat Agent 只能使用内建工具，`/mcp` 仍是占位页，用户无法持久管理、真实检查或调用自己的 MCP Server。现在需要在 owner scope、安全审计和有界失败语义下建立单一真实 MCP 连接来源，供 Chat 与后续 AIOps 共用。

## What Changes

- 使用 Alembic 新增 owner-scoped `mcp_connections`，保存连接参数、启停状态、最近真实检查结果和工具发现快照。
- 新增 MCP 连接 CRUD 与 check API；后端权威校验 transport、URL、timeout/retry，check 必须连接真实 Server 并返回真实 tools 或显式失败。
- 建立基于 `langchain-mcp-adapters`/MCP client 的可注入 gateway，按当前 owner 聚合 enabled 连接；禁用连接不连网，工具同名冲突使整个装配明确失败。
- 用户没有 enabled 持久连接时，才允许把本地 JSON 中非空 `clsMcpServer.baseUrl` 作为真实临时回退连接；不生成假 profile、假工具或假结果。
- 把请求级真实 MCP tools 注入 Chat Agent，复用共享 `tool.call` SSE 和 owner-scoped audit；MCP 审计/日志只保留工具名、参数键、状态、耗时和安全摘要。
- 用共享 contracts 定义 MCP DTO、错误和 OpenAPI operations，并实现 typed client、Pinia store 与真实 `/mcp` 桌面管理页。
- 文档明确 URL 完整持久化且当前不支持自定义 headers，因此禁止在 query 放 token/secret；官方 CLS MCP Server 仍在主机运行，P26 再完成启动与凭据细节。
- 产品运行时禁止 mock MCP profile、假工具目录或假调用结果；自动化测试只能通过注入的可控 transport 替身验证边界。

## Capabilities

### New Capabilities

- `mcp-connection-and-tool-management`: 定义 owner-scoped MCP 连接持久化、真实发现/调用、冲突检测、CLS 真实回退与桌面管理页。

### Modified Capabilities

- `agentic-rag-chat-streaming`: 每轮 Chat 装配当前 owner 的真实 enabled MCP tools，不因 MCP 失败伪造或静默降级。
- `agent-tool-call-auditing`: MCP 工具调用复用通用审计，但只持久化参数键与安全摘要，不复制敏感值或完整输出。
- `api-and-sse-contracts`: 增加 MCP DTO、五个受保护 operations、稳定错误与前后端对齐约束。
- `chinese-vue-app-shell`: 把 `/mcp` 占位画布替换为可访问的桌面连接管理工作区。
- `monorepo-foundation`: 明确 MCP/CLS 本地 JSON 回退配置、URL 凭据禁止与主机运行文档边界。

## Impact

- 后端：Alembic/SQLAlchemy、不可变 records、Repository Protocol/SQLite adapter、MCP gateway/client factory、FastAPI router/dependencies、Chat tool assembly 与 audit sanitizer。
- 合同：TypeScript/Pydantic MCP DTO、上传以外的 JSON 请求、OpenAPI path/error 目录与跨语言测试。
- 前端：`mcpClient`、受保护 Pinia store、`McpView` 及桌面列表/编辑/检查交互。
- 配置/文档：深合并后的 `clsMcpServer` typed 回退边界、主机运行说明与真实 smoke 记录；Compose 服务白名单不变。
