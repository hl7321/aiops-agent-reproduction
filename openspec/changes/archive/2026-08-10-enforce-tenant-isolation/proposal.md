## Why

P04 已建立可认证用户，但后续资源如果先按资源 ID 查询、再在 service 层补 owner 检查，会形成可枚举和跨用户访问风险。P05 必须在任何 Chat、知识、向量或后台任务领域落地前，把当前用户身份固化为强制 tenant/owner scope。

## What Changes

- 定义 `CurrentUser`、`OwnerScope` 与 tenant context；当前本地模型中 `tenant_id` 等于当前 `user_id`，但保留两个语义字段。
- 建立 owner-scoped Repository Protocol、参数级治理检查和 SQLite scope helper，受保护查询、更新、删除必须在数据库语句中同时包含 `owner_user_id`。
- 规定直接资源不存在与跨用户访问使用不可枚举的同一 not-found 语义；受保护父资源不存在或越权统一返回 `AUTH_FORBIDDEN` 403，禁止额外无 scope 查询探测存在性。
- 扩展共享 contracts/OpenAPI，为所有受保护 path 固化 `BearerAuth`、401 与 403 复用模式。
- 建立纯函数 Milvus filter/metadata/delete-scope 约定：搜索只使用 `tenantId + allowedKnowledgeBaseIds`；空 KB scope 不连接 Milvus；可选文档/metadata 条件只在召回后过滤；删除必须同时包含 tenant、KB 与 document。
- 明确 logout 只撤销认证并清理客户端可见状态，不删除用户持久数据。
- 在项目指南与架构文档中声明 Chat、Knowledge、Index Jobs、Vector、MCP、AIOps、Evidence、Reports、Cases、Feedback、Audit 和 Background Jobs 必须遵守 tenant 边界。
- 本变更不实现上述产品领域的表、CRUD、Milvus 连接或检索业务。

## Capabilities

### New Capabilities

- `tenant-isolation`: 定义当前用户 tenant 语义、owner-scoped Repository、不可枚举错误、SQLite scope 与向量 filter/delete 边界。

### Modified Capabilities

- `api-and-sse-contracts`: 为受保护 OpenAPI path 增加统一 bearer、401、403 合同模式。
- `sqlite-repository-foundation`: 将未来受保护 Repository 的 owner 参数和数据库语句 scope 固化为持久化基础约束。
- `user-authentication`: 明确认证后的 CurrentUser/tenant 映射，以及 logout 不删除用户持久数据。

## Impact

- 后端新增 `super_ai.tenancy` 领域边界、SQLite 查询 helper、向量 scope builder、错误映射与双用户合同测试；不新增 Alembic revision。
- `packages/api-contracts` 增加受保护 path policy 和稳定资源不可枚举错误；现有 `/auth/logout`、`/auth/me` OpenAPI 响应合同扩展 401/403。
- 前端认证状态行为保持兼容，并用回归测试证明 logout 只清理客户端状态。
- `AGENTS.md` 与架构文档新增所有未来领域的强制 tenant/owner 规则。
