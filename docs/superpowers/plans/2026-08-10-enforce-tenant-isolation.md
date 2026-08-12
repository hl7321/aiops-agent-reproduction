# Enforce Tenant Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前认证用户固化为不可绕过的 tenant/owner scope，并为未来 SQLite 与 Milvus 资源访问建立双用户隔离合同。

**Architecture:** `super_ai.tenancy` 保存 CurrentUser、OwnerScope、TenantContext、Repository Protocol、错误语义和纯向量 filter；`super_ai.memory.sqlite.owner_scope` 只负责把 owner 与资源/父子标识组合到同一个 SQL 语句。共享 contract manifest 统一受保护 OpenAPI path 的 BearerAuth、401、403；不创建产品表或外部 client。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy 2 async、aiosqlite、pytest、Ruff、strict Pyright；TypeScript 5.6 strict、Vitest 2。

## Global Constraints

- 所有受保护 Repository 方法显式接收 `owner_user_id`；禁止按 ID 裸查后补 service 检查。
- 当前 `tenant_id == owner_user_id == user_id`，但向量 metadata 同时保留 `tenantId` 和 `ownerUserId`。
- 直接资源缺失/跨 owner 使用同一 404；父资源缺失/越权使用同一 403，不做无 scope 探测。
- Milvus 搜索 scope 只有 tenant + allowed KB；空 KB 不调用外部连接；删除必须 tenant + KB + document。
- 不新增业务表、migration、真实 Milvus 连接或产品 CRUD。
- 先观察失败测试，再写最小实现；完整门禁和 verify 后才同步/归档。

---

### Task 1: 扩展受保护 OpenAPI 合同

**Files:**
- Modify: `packages/api-contracts/contract-manifest.json`
- Modify: `packages/api-contracts/src/openapi.ts`
- Modify: `packages/api-contracts/src/index.test.ts`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Modify: `apps/backend/src/super_ai/auth/router.py`
- Test: `apps/backend/tests/test_contract_manifest.py`

**Interfaces:**
- Produces: `PROTECTED_PATH_POLICY`，受保护 path `errors`，`BUSINESS_RESOURCE_NOT_FOUND`。

- [ ] 编写 manifest 测试：任何 `security: ["BearerAuth"]` path 必须含 `AUTH_REQUIRED` 与 `AUTH_FORBIDDEN`。
- [ ] 运行 contracts test，确认因 policy/error 缺失而失败。
- [ ] 扩展 manifest/TS/Pydantic，并给 `/auth/logout`、`/auth/me` 登记 FailureEnvelope 401/403。
- [ ] 运行 contracts 与后端 manifest 测试并确认通过。

### Task 2: 建立 tenant value objects 与 Repository 治理

**Files:**
- Create: `apps/backend/src/super_ai/tenancy/context.py`
- Create: `apps/backend/src/super_ai/tenancy/repositories.py`
- Create: `apps/backend/src/super_ai/tenancy/dependencies.py`
- Test: `apps/backend/tests/tenancy/test_context.py`
- Test: `apps/backend/tests/tenancy/test_repository_contract.py`

**Interfaces:**
- Produces: `CurrentUser`、`OwnerScope`、`TenantContext`、`OwnerScopedRepository`、签名验证器。

- [ ] 编写相等 scope 与空/不一致拒绝测试，确认 import 失败。
- [ ] 实现 frozen value objects 和从 AuthPrincipal 派生的 dependency。
- [ ] 编写缺少/错位 `owner_user_id` 会被签名验证器拒绝的测试并观察失败。
- [ ] 实现 Protocol/验证器并运行目标测试。

### Task 3: 建立 SQLite scoped helper

**Files:**
- Create: `apps/backend/src/super_ai/memory/sqlite/owner_scope.py`
- Create: `apps/backend/src/super_ai/tenancy/errors.py`
- Test: `apps/backend/tests/tenancy/test_sqlite_owner_scope.py`

**Interfaces:**
- Consumes: Task 2 `OwnerScope`。
- Produces: scoped select/update/delete/child statement builder 与 404/403 error mapper。

- [ ] 在测试专用 Base 中建立两个 owner 和同类资源/父子数据，写 read/update/delete 越权测试。
- [ ] 运行目标 pytest，确认 helper 缺失导致失败。
- [ ] 实现所有 SQL builder，把 owner、resource、parent 条件放入同一 WHERE，并拒绝空 owner。
- [ ] 断言另一个用户的 record 不返回、不更新、不删除；错误 body 不含 owner 细节。

### Task 4: 建立纯 Milvus scope/filter 合同

**Files:**
- Create: `apps/backend/src/super_ai/tenancy/vector_scope.py`
- Test: `apps/backend/tests/tenancy/test_vector_scope.py`

**Interfaces:**
- Produces: `VectorScope`、`build_vector_metadata`、`build_search_filter`、`scoped_vector_search`、`post_filter_hits`、`build_delete_filter`。

- [ ] 用手工字面量写 filter/metadata 期望，覆盖 JSON quoting 和 protected key 覆盖。
- [ ] 写空 KB 回调抛错测试，确认生产函数缺失而红灯。
- [ ] 实现只含 tenant/KB 的搜索 filter 和空列表提前返回。
- [ ] 实现召回后 document/metadata filter 与完整三字段 delete filter，运行目标测试。

### Task 5: 回归 logout 与项目治理

**Files:**
- Modify: `apps/backend/tests/auth/test_api.py`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Create: `docs/architecture/tenant-isolation.md`
- Modify: `tests/test_foundation_structure.py`

**Interfaces:**
- Consumes: 已有 auth API/session。
- Produces: logout 不删除持久用户的证据与未来领域治理规则。

- [ ] 扩展双 session 集成测试：logout 后 users row 仍存在且重新登录可访问 `/auth/me`。
- [ ] 运行目标测试并确认既有实现满足；若测试立即通过，记录其为回归特征而非 TDD 新行为。
- [ ] 更新简体中文项目/架构文档，列全 Chat、Knowledge、Index Jobs、Vector、MCP、AIOps、Evidence、Reports、Cases、Feedback、Audit、Background Jobs。
- [ ] 增加结构治理测试，证明 tenant package import-safe 且没有新增产品表/revision。

### Task 6: 完整验证和归档

**Files:**
- Modify: `openspec/changes/enforce-tenant-isolation/tasks.md`
- Sync: `openspec/specs/tenant-isolation/spec.md`
- Sync: 三份 modified main specs。

**Interfaces:**
- Produces: 0 CRITICAL/0 WARNING verify、同步主规格和 P05 归档。

- [ ] 运行 backend `uv run ruff check .`、`uv run pyright`、`uv run pytest`。
- [ ] 运行 contracts/frontend typecheck/test/build、`openspec validate --all`、`git diff --check`。
- [ ] 逐 requirement/scenario 执行 verify；修复问题并重跑完整门禁。
- [ ] 智能同步全部 delta，逐项比对后归档并再次验证 specs。
