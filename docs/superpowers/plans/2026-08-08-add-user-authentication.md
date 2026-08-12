# Add User Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 P02/P03 边界上实现邮箱/密码注册登录、可撤销 opaque bearer session、当前用户和前端认证恢复。

**Architecture:** `super_ai.auth` 保存无 ORM 的 record、Protocol 与服务；`super_ai.memory.extended_sqlite` 保存认证 ORM/repository；FastAPI 通过显式 persistence lifespan 和每请求 dependency 组装服务。TypeScript contracts 是 HTTP/Auth 形状的事实来源，前端 authClient/Pinia state 只把 raw bearer token 写入 localStorage。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy 2 async、aiosqlite、Alembic、pwdlib[argon2]、pytest；TypeScript 5.6 strict、Vue 3.5、Pinia 3、Vitest 2。

## Global Constraints

- 先写验收测试并观察目标失败，再写最小实现。
- 后端只允许 `from super_ai...`；import 期间不得连接 SQLite 或动态计算密码 hash。
- Alembic 是 schema 唯一权威；运行期禁止 `metadata.create_all`。
- 明文密码和 raw token 不得保存或记录；SQLite token hash 必须是 64 位 SHA-256 十六进制值。
- 当前版本无自动过期、刷新 token、完整页面或服务端业务数据删除。
- OpenSpec 文档使用简体中文；完整门禁和 verify 通过后才能同步/归档。

---

### Task 1: 扩展 Auth 单一事实来源

**Files:**
- Create: `packages/api-contracts/src/auth.ts`
- Modify: `packages/api-contracts/src/index.ts`
- Modify: `packages/api-contracts/src/manifest.ts`
- Modify: `packages/api-contracts/src/openapi.ts`
- Test: `packages/api-contracts/tests/contracts.test.ts`

**Interfaces:**
- Produces: `AuthUser`、`RegisterRequest`、`LoginRequest`、`LoginData`、`LogoutData`、`BearerAuth` 和四个 auth path manifest。

- [ ] 编写断言 `AUTH_INVALID_CREDENTIALS`/重复邮箱错误、Auth DTO、四个 path 与受保护 path `BearerAuth` 的测试。
- [ ] 运行 `npm run contracts:test`，确认因 Auth exports/manifest 缺失而失败。
- [ ] 实现上述类型与 manifest，保持类型中无密码 hash/session ORM 字段。
- [ ] 运行 `npm run contracts:typecheck && npm run contracts:test`，确认通过。

### Task 2: 建立认证 migration 与 repository

**Files:**
- Create: `apps/backend/src/super_ai/auth/models.py`
- Create: `apps/backend/src/super_ai/auth/repositories.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/auth_models.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/auth_repositories.py`
- Create: `apps/backend/migrations/versions/*_add_user_authentication.py`
- Modify: `apps/backend/src/super_ai/memory/sqlite/base.py`
- Test: `apps/backend/tests/auth/test_migration.py`
- Test: `apps/backend/tests/auth/test_repositories.py`

**Interfaces:**
- Produces: `UserRecord`、`AuthSessionRecord`、`UserRepository`、`AuthSessionRepository` 与 SQLite adapter。

- [ ] 编写 fresh upgrade、metadata 对齐、唯一邮箱、owner 不匹配不更新、record 不可变的测试。
- [ ] 运行目标 pytest，确认因表/repository/revision 缺失而失败。
- [ ] 实现规范化表、唯一/外键/长度约束、UTC 映射和 owner-safe repository。
- [ ] 运行 migration/repository 测试并确认通过。

### Task 3: 实现密码与 AuthService

**Files:**
- Create: `apps/backend/src/super_ai/auth/passwords.py`
- Create: `apps/backend/src/super_ai/auth/tokens.py`
- Create: `apps/backend/src/super_ai/auth/service.py`
- Modify: `apps/backend/pyproject.toml`
- Modify: `apps/backend/uv.lock`
- Test: `apps/backend/tests/auth/test_service.py`

**Interfaces:**
- Consumes: Task 2 repositories。
- Produces: `AuthService.register/login/authenticate/logout`、`AuthPrincipal`、`LoginResult`。

- [ ] 编写邮箱规范化、Argon2 非明文、重复邮箱、正确/错误/未知登录统一错误与 dummy verifier 调用测试。
- [ ] 编写 raw token 仅返回一次、SHA-256 持久化、lastSeen 和 revoke 测试并观察失败。
- [ ] 添加 `pwdlib[argon2]`，实现预生成 dummy hash、`secrets.token_urlsafe(48)` 与服务方法。
- [ ] 运行服务测试并确认未知账号也调用 verifier、数据库不含 raw token。

### Task 4: 暴露统一 FastAPI 认证 API

**Files:**
- Create: `apps/backend/src/super_ai/auth/api_models.py`
- Create: `apps/backend/src/super_ai/auth/dependencies.py`
- Create: `apps/backend/src/super_ai/auth/router.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Test: `apps/backend/tests/auth/test_api.py`
- Test: `apps/backend/tests/test_contract_manifest.py`

**Interfaces:**
- Produces: `POST /auth/register`、`POST /auth/login`、`POST /auth/logout`、`GET /auth/me`。

- [ ] 用临时 migrated SQLite 编写四路由、request ID、统一错误、撤销后 401 与 CORS 预检测试。
- [ ] 运行 API 测试，确认因路由/dependency 缺失而失败。
- [ ] 实现显式 runtime lifespan、HTTPBearer dependency、Pydantic DTO/router/CORS，不在启动时迁移。
- [ ] 比较 FastAPI OpenAPI 的 operationId/security 与 TypeScript manifest，并运行 API/合同测试。

### Task 5: 实现前端 authClient 和 Pinia state

**Files:**
- Create: `apps/frontend/src/api/authClient.ts`
- Create: `apps/frontend/src/stores/auth.ts`
- Modify: `apps/frontend/src/main.ts`
- Test: `apps/frontend/src/api/authClient.test.ts`
- Test: `apps/frontend/src/stores/auth.test.ts`

**Interfaces:**
- Consumes: Task 1 Auth contracts 与现有 `ApiClient`。
- Produces: typed `AuthClient` 与可测试 `createAuthStore`/生产 `useAuthStore`。

- [ ] 编写 register/login/logout/me 请求形状和 bearer 注入测试并观察失败。
- [ ] 编写 localStorage 仅 token、有效恢复、401 清理、网络失败保留 token、logout 清理回调测试并观察失败。
- [ ] 实现 authClient 与注入 storage/client/clearProtectedState 的 Pinia store，完整页面留给 P08。
- [ ] 运行 `npm run frontend:typecheck && npm run frontend:test && npm run frontend:build`。

### Task 6: 完整验证与 OpenSpec 生命周期

**Files:**
- Modify: `openspec/changes/add-user-authentication/tasks.md`
- Sync after verification: `openspec/specs/user-authentication/spec.md`
- Sync after verification: `openspec/specs/api-and-sse-contracts/spec.md`

**Interfaces:**
- Consumes: Tasks 1–5 全部实现与测试证据。
- Produces: 无 CRITICAL 的 verify 报告和已归档 P04 change。

- [ ] 在 `apps/backend` 运行 migration head、`uv run ruff check .`、`uv run pyright`、`uv run pytest`。
- [ ] 在仓库根运行 contracts/frontend 受影响门禁、`openspec validate --all`、`git diff --check`。
- [ ] 按 `$openspec-verify-change` 检查完整性、正确性和一致性，修复 CRITICAL 并处理 WARNING 后重新执行门禁。
- [ ] 使用 `$openspec-archive-change` 同步 delta specs、归档，再执行 `openspec validate --all` 和 `git diff --check`。
