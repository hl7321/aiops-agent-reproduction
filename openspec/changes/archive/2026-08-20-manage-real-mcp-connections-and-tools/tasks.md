## 1. 合同与验收测试先行

- [x] 1.1 先在 `packages/api-contracts` 增加失败测试，覆盖 MCP connection、transport、工具摘要、检查结果、CRUD 请求/响应、URL/timeout/retries 边界和共享错误码。
- [x] 1.2 扩展共享 TypeScript contracts 与机器可读 OpenAPI manifest，声明 `GET/POST /mcp/connections`、`PUT/DELETE /mcp/connections/{id}`、`POST /mcp/connections/{id}:check` 及 bearer、401、403、409、502 复用模式，使合同测试通过。
- [x] 1.3 先在后端增加 Pydantic DTO、错误目录和 OpenAPI path 的失败测试，证明后端 envelope、字段命名、枚举和共享合同一致。

## 2. SQLite 迁移与 owner-scoped Repository

- [x] 2.1 先编写迁移测试，覆盖 fresh upgrade、metadata 一致性、约束、索引和 downgrade，再增加 `mcp_connections` Alembic migration。
- [x] 2.2 定义不可变 MCP connection record、owner-first Repository Protocol 和 ORM model；领域服务不得接收 ORM model 或 `AsyncSession`。
- [x] 2.3 在 `super_ai.memory.extended_sqlite` 实现 owner-scoped list/get/create/update/delete/check-state 持久化，保证 name 在 user 内唯一且跨 user 不可枚举。
- [x] 2.4 增加 Repository 合同测试，覆盖两个用户 CRUD、同名冲突、启停、检查快照、事务回滚、删除和 import-safety。

## 3. URL 安全、真实 MCP gateway 与 CLS 回退

- [x] 3.1 先编写 URL 与配置失败测试，覆盖仅允许 HTTP/HTTPS、必须有 host、拒绝 userinfo、保留 path/query、范围校验，以及日志和错误不得泄露完整 URL/query。
- [x] 3.2 实现 typed MCP connection 校验和安全错误摘要；文档与 DTO 明确当前不支持自定义 headers，禁止在 URL query 中放置 token/secret。
- [x] 3.3 定义可注入 MCP client/gateway 边界，并用 `langchain-mcp-adapters` 的真实 client 实现 SSE 与 Streamable HTTP 工具发现和调用；模块 import、disabled connection 和无工具请求不得连接网络。
- [x] 3.4 先写 gateway 失败测试，再实现检查/发现阶段的有界 timeout 与 `retries + 1` 次尝试、确定性退避、失败显式返回和工具调用不自动重试，证明有副作用的工具不会重复调用。
- [x] 3.5 增加多连接聚合测试与实现：不同 server 或与内置工具发生同名冲突时返回 `BUSINESS_MCP_TOOL_NAME_CONFLICT`，不得随机选择。
- [x] 3.6 完善 `clsMcpServer` typed 配置和模板：增加 transport、timeoutSeconds、retries；仅在当前 user 没有 enabled connection 时创建真实临时回退来源，禁止生成假 profile、假工具或假结果。
- [x] 3.7 增加配置、脱敏和 import-safety 测试，扫描模板与运行日志，确保 secret 默认空且 client 只在显式调用路径创建。

## 4. MCP 应用服务与 FastAPI API

- [x] 4.1 实现 owner-scoped MCP connection service，统一 CRUD、真实 check、工具快照和 lastCheck/lastError 更新语义。
- [x] 4.2 实现三条 MCP path pattern 的五个 HTTP operation，全部使用统一 envelope、request id、认证依赖和共享错误目录。
- [x] 4.3 增加 API 测试，覆盖创建、列表、编辑、启停、删除、真实发现替身、连接失败诊断、timeout/retry、同名冲突、两个用户隔离和安全错误信息。

## 5. Chat Agent、SSE 与工具审计集成

- [x] 5.1 先增加 Chat 失败测试，覆盖只装配当前 user 的 enabled MCP tools、disabled 不连接、CLS 回退、模型不选择时不调用、模型选择时真实调用和全局同名冲突。
- [x] 5.2 把 request-scoped MCP tool factory 接入现有 `create_agent` 组装路径，与 `knowledge_retrieval`、`get_current_time`、`load_skill` 共用统一工具来源和冲突检查，禁止 Agent 前预调用 MCP。
- [x] 5.3 复用现有 `tool.call` SSE lifecycle 和通用 tool-call audit；MCP arguments、事件和结构化日志只保留参数键与 `[provided]` 标记，结果只保存安全摘要。
- [x] 5.4 增加 Chat/Audit 测试，覆盖 started/completed/failed、耗时、owner 与 chat parent、错误转共享 SSE error、失败无半条 assistant message、日志无 URL/query/参数值/工具输出。

## 6. Vue MCP 管理工作区

- [x] 6.1 先在前端增加 typed `mcpClient` 与 Pinia store 失败测试，覆盖 bearer/envelope、CRUD、启停、check、真实工具列表、错误状态和认证清理。
- [x] 6.2 实现 `mcpClient`、MCP store 和 `/mcp` 数据加载生命周期，以服务端为唯一事实来源，不使用 localStorage、静态数组或产品运行时 mock。
- [x] 6.3 用真实管理页替换 `/mcp` placeholder，提供连接列表、新建/编辑/删除、SSE/Streamable HTTP 选择、启停、timeout/retries、检查状态和实际发现工具展示。
- [x] 6.4 增加组件与路由测试，覆盖中文 loading/empty/error/status、确认操作、URL 安全提示、键盘/focus/ARIA、桌面有界滚动和未知/401 状态清理；不新增移动专用替代流程。

## 7. 文档、完整验证与归档

- [x] 7.1 更新中文 README、架构/安全说明和 MCP 运行说明：官方 `cls-mcp-server` 在主机运行，P18 不提供启动/凭据教程，该内容留给 P26；未完成真实 smoke 时不得声称连通。
- [x] 7.2 执行 `cd apps/backend && uv run alembic upgrade head && uv run ruff check . && uv run pyright && uv run pytest`，修复全部问题。
- [x] 7.3 执行 `npm run contracts:typecheck && npm run contracts:test && npm run frontend:typecheck && npm run frontend:test && npm run frontend:build && npm run frontend:test:secret`，修复全部问题。
- [x] 7.4 执行 `docker compose -f infra/compose.yaml config`、`openspec validate --all` 和 `git diff --check`，确认现有基础设施边界与规格一致。
- [x] 7.5 在官方 CLS MCP 服务与凭据可用时执行真实 discovery 与 Chat tool-call smoke，并记录实际结果；不可用时明确记录“未执行”及原因，不能用 fake transport 代替真实 smoke 结论。
- [x] 7.6 使用 `$openspec-verify-change` 检查完整性、正确性和设计一致性；修复 CRITICAL 并处理 WARNING 后重新运行相关门禁。

归档动作：验证通过后同步 delta specs 到主规格，并使用 `$openspec-archive-change` 归档 `manage-real-mcp-connections-and-tools`。该动作属于本清单完成后的生命周期操作，不作为归档前任务复选框。
