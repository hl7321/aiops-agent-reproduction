## Context

参见 [proposal.md](./proposal.md) 的动机。P15 已经用 LangChain 1.x `create_agent` 建立请求级工具装配、共享 SSE 事件和通用审计；P16/P17 又固定了 Prompt/Skill/memory snapshot。P18 必须作为该 tool factory 的扩展，不能建立第二套 Agent、SSE 或 audit 运行时。

当前依赖已包含 `langchain-mcp-adapters>=0.1,<1` 和 `mcp>=1,<2`。当前 adapter 的 `MultiServerMCPClient.get_tools()` 会为 discovery 和每次 tool call 创建临时 session，它不是 async context manager，也没有需要伪造的 public `close()` 合同。它支持 `sse` 与 `streamable_http`，但本产品模型明确不向用户暴露 custom headers。

还需继续遵守：模块 import 不读取配置、不连接 MCP；所有连接与 client 只能由 FastAPI dependency/显式 factory 在运行期创建；服务端 JSON 配置和凭据不得进入浏览器 bundle；官方 CLS MCP Server 仍在主机运行而不加入 Compose。

## Goals / Non-Goals

**Goals:**

- 建立可供 Chat 和后续 AIOps 共用的 owner-scoped MCP connection source 与 gateway Protocol。
- 让 CRUD、check、Agent discovery 和真实 tool invocation 具有一致的 URL、timeout、retry、冲突和脱敏语义。
- 保持产品运行时只调用真实 MCP 协议 client，同时使自动化测试可通过 Protocol 注入可控替身。
- 把 `/mcp` 实现为服务器事实来源的桌面工作区，不扩展移动导航。

**Non-Goals:**

- 不支持 stdio、websocket、custom headers、OAuth 或浏览器直连 MCP Server。
- 不实现 MCP resource/prompt 消费、长连接池、背景健康轮询或自动工具名前缀。
- 不将凭据放入连接记录，不完成 P26 的官方 CLS MCP Server 安装、启动、凭据注入或 SOP 流程。
- 不将可能产生副作用的真实 tool invocation 自动重试，不用重试伪装幂等性。

## Decisions

### 1. 连接事实使用规范化主表，discovery 是有界 JSON 快照

Alembic revision `20260820_0010_add_mcp_connections.py` 新增 `mcp_connections`：

- `id`、`owner_user_id`、`name`、`transport`、`url`、`enabled`；
- `timeout_seconds`、`retries`；
- `last_check`、`last_error`、`discovered_tools`；
- `created_at`、`updated_at`。

建立 `(owner_user_id, name)` 唯一约束、owner/list 索引、transport/range check 约束。`discovered_tools` 只保存最近成功 check 的有界 name/description 快照，不参与跨资源查询，因此使用统一 JSON serializer 而不过度拆表。目录最多保存 500 个工具，name 最长 255 字符、description 最长 2000 字符；越界目录按安全 check 失败处理并清空快照，避免响应模型在持久化后才失败，也避免 UI 把旧工具当成当前真实结果。

备选是为每个 discovered tool 创建子表。当前产品不按 tool 字段做 SQL 过滤/关联，且 discovery 必须每次以真实 Server 为权威，子表会制造多余的 catalog 事实语义，不采用。

### 2. URL 原样返回，但所有非 DTO 披露都移除 query

一个纯 `validate_mcp_url` 边界解析 URL：仅 http/https、必须有 hostname、禁止 username/password。path/query 不重写，因为 MCP endpoint 可依赖它们；owner-scoped CRUD DTO 明确返回完整 URL。同时 `safe_mcp_error` 只返回错误类别与脱敏文本，要从异常中替换完整 URL、query、已知 API key/secret；运行日志只记 owner/id/transport/attempt/status，不记 URL。

页面在 URL 输入旁显示“完整 URL 会保存并返回，禁止将 token/secret 写入 query”。当前不设计 headers 字段，避免做一个未加密凭据库。

备选是禁止所有 query。这会错误拒绝合法 endpoint 路由，且与用户明确要求“完整 URL 持久化并返回”冲突，不采用。

### 3. Repository/Service/Gateway 分层供 Chat 与 AIOps 共用

`super_ai.mcp_connections` 按职责拆分：

- 不可变 `McpConnectionRecord` 与 create/update/check records；
- `McpConnectionRepository` Protocol，所有业务方法第一参数为 `owner_user_id`；SQLite adapter 放在 `super_ai.memory.extended_sqlite`；
- `McpConnectionService` 处理 CRUD/check 事务、业务错误与快照写回；
- `McpToolGateway` Protocol 只接收不可变 connection source，返回 `McpToolSet(tools, mcp_tool_names)`，Chat/AIOps 不依赖 SQLite 或 adapter 细节。

这使后续 AIOps 可在 diagnostic task request scope 复用同一 source/gateway，而不复制连接表或伪造第二 catalog。

### 4. 生产 gateway 使用当前 adapter 的临时 session 生命周期

`LangChainMcpToolGateway` 为每条 connection 创建只含一个 server 的 `MultiServerMCPClient`，连接配置只包含 `transport`、`url`、`timeout`与对应 SSE read timeout，不传 headers。每次 `get_tools(server_name=...)` 都使用 adapter 自身临时 session；返回的 LangChain tools 在真实 invocation 时也由 adapter 新建 session。不把 client 作为 context manager，不调用不存在的 `close()`。

为可测试性，网关接收 `McpClientFactory` Protocol；生产 factory 唯一允许的实现使用 `MultiServerMCPClient`，单测可注入 fake client。模块 import 只定义类和 factory，不读配置、不创建 client、不连网。

备选是在 lifespan 建立长连接池。当前 adapter 和产品没有稳定 close/reconnect 合同，而且 owner 可随时修改连接，请求级临时 session 更符合正确性，不采用池。

### 5. retries 只重试 discovery/handshake，真实 tool invocation 不自动重放

check 和 Agent tool assembly 对每条 Server 执行最多 `retries + 1` 次 `get_tools`，每次同时受 adapter timeout 和 `asyncio.timeout(timeoutSeconds)` 约束；仅在失败后进入下一次尝试，成功后立即停止，因此不会返回重复 tools。重试间隔使用有界指数退避 `min(0.1 * 2^attempt, 1.0)`，测试可注入 sleep。

工具实际 invocation 只由模型的一次 tool call 驱动，不使用 connection.retries 重放；仍由 adapter connection timeout 有界终止。原因是 MCP tool 可能修改外部系统，自动重试会造成重复副作用。这也是“不重复调用”的权威解释。

备选是所有 tool call 也按 retries 重试。在没有工具级幂等 key 合同时不安全，不采用。

### 6. 工具名冲突使整个快照失败

网关先为每个 Server 独立发现，再以原始 `BaseTool.name` 聚合。任意两个 MCP Server 同名，或 MCP tool 与当前内建 tool 同名，都抛出 `BUSINESS_MCP_TOOL_NAME_CONFLICT` 409，details 只包含冲突工具名，不包含 URL。不启用 adapter 的自动 server prefix，因为用户明确要求同名直接报错，且自动改名会使 Prompt/audit 名称不稳定。

connection name 在 owner 内冲突复用 `BUSINESS_CONFLICT` 409；连接/discovery 耗尽重试使用 `SYSTEM_MCP_CONNECTION_FAILED` 502，默认消息不包含 URL 或 provider 原始异常。

### 7. check 是 200 的诊断结果，不把可预期连通失败伪装成 HTTP 成功能力

check 必须让 UI 同时获得刷新后连接和诊断状态。因此，连接成功与可预期的超时/Server 失败都返回 200 success envelope 中的 `McpConnectionCheckResult`：`status=connected|failed`、`connection`、`tools`、`error`。failed 不表示工具已可用；页面必须以文字展示失败。认证、owner、validation 和未处理内部异常仍使用 HTTP failure envelope。

备选是 check 失败直接返回 502。这会让成功持久化的 lastCheck/lastError 无法在同一 typed 响应中对账，且会将“诊断结果为失败”与“API 自身失败”混淆，不采用。

### 8. CLS 回退是未持久化真实 source，且只在 owner 无 enabled 连接时生效

`ClsMcpServerSettings` 从本地 JSON 深合并结果读取 `baseUrl`、`transport`、`timeoutSeconds`、`retries`；模板默认分别为空、`streamable_http`、30、1。`secretId/secretKey` 保留供 P26 启动官方主机 Server 时使用，P18 MCP client 绝不读取或发送它们。

connection source 先查 owner enabled records；非空时忽略 CLS fallback。为空且 baseUrl 有效时在内存构造 `McpConnectionTarget`，但不写入 `mcp_connections`、不出现在 CRUD 列表；baseUrl 为空时返回空 target 且不创建 client。

备选是启动时给每个用户插入默认 CLS profile。这会产生假持久化记录、与配置漂移并误导 UI，不采用。

### 9. Chat 复用现有 runner/SSE/audit，通过 tool source metadata 缩小披露

Chat dependency 在创建 `ConfiguredAgentTurnRunner` 前，并行准备内建 tools 与 owner MCP tool set，然后做全局名称冲突检测。MCP tools 仍交给现有 `AgentChatRunner`，因此真实调用自然产生 P15 `tool.call` 和 audit 生命周期，不新增 MCP-specific SSE type。

`McpToolSet` 另外返回 `mcp_tool_names`。runner 对这些名称使用 keys-only sanitizer：审计 arguments 和 started SSE input 只包含 `{key: "[provided]"}`；成功审计只保存“MCP 工具调用成功”等有界摘要，不复制工具输出。内建工具保留既有 P15 审计合同，避免不必要的破坏性变更。

备选是为 MCP 创建第二套 SSE/audit。这会破坏单一工具生命周期事实来源，不采用。

### 10. `/mcp` 使用实体列表 + 行内编辑/详情，不建移动替代流程

`mcpClient` 直接消费共享 DTO 与 envelope；`mcp` Pinia store 管理 connections、editingId、checkById、loading/error，每次 mutation 都以服务端响应替换对应记录。store 注册 protected cleanup，并用认证世代号阻止 logout、401 或卸载后的在途旧响应重新写入已清理状态；更新连接时清除该连接的旧检查快照。MCP 状态不写 localStorage。

`McpView` 使用桌面两列/有界表格布局：顶部说明凭据禁止；列表提供启停、编辑、检查、删除；表单提供 name、transport、URL、timeout/retry；行内展开区显示 lastCheck/lastError 与有界工具列表。删除需要明确确认，启停使用同一 update operation，不另造 endpoint。沿用共享 loading/empty/error/status/feedback 与 focus/reduced-motion tokens。

## Risks / Trade-offs

- [MCP tool 在 discovery 后到 invocation 前变化] → adapter 每次调用新建 session；调用失败显式通过 SSE/audit 报告，不用旧快照伪造成功。
- [多个 enabled Server 使请求准备变慢] → Server 之间并行 discovery，每个 Server 内部有界重试；不为性能静默跳过失败连接。
- [完整 URL 返回可能暴露用户误放的 query 凭据] → 后端/UI/文档明确禁止；禁止 userinfo；日志、错误与审计不回显 URL/query。当前按用户需求不删除合法 query。
- [短生命周期 session 增加握手开销] → 优先与当前 adapter 官方生命周期一致；等未来有可验证 close/reconnect 合同再评估连接池。
- [不重试真实 tool invocation 降低短暂故障容错] → 避免重复外部副作用；失败可见，由用户/模型发起新的显式调用。
- [CLS fallback 不出现在 CRUD UI] → 它只是本地运行回退配置，不是用户资产；UI 不声称存在一条未持久化 profile。

## Migration Plan

1. 先扩展共享 contracts/错误/manifest，再增加 Alembic `0010`、ORM/records/Repository 与 fresh/upgrade/downgrade 测试。
2. 实现纯 URL/脱敏/冲突函数和可注入 gateway，用 fake client 先覆盖 timeout/retry/disabled/冲突，然后接 FastAPI CRUD/check。
3. 把 typed CLS fallback settings 接入 app runtime，扩展 Chat tool assembly 与 keys-only MCP audit/SSE sanitizer，保持既有内建 tools 测试不变。
4. 实现前端 client/store/page 和路由，更新 README/主机运行说明，不新增 Compose 服务。
5. 运行全量门禁；若本机官方 CLS MCP Server 和所需凭据可用，执行真实 discovery + Chat tool call smoke，否则明确记录未执行。

回滚时前端恢复 MCP 占位路由、Chat 不再装配 MCP tools，Alembic downgrade 删除 `mcp_connections`。连接表不存放凭据，回滚不会删除服务端外部业务数据。
