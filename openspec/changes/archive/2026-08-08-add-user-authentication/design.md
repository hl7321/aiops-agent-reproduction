## Context

P02 已把 HTTP envelope、错误目录、request ID 与机器可读 OpenAPI path 设为共享合同，P03 已建立异步 SQLite、Alembic、Repository Protocol 与运行期注入边界。P04 需要在不绕过这些边界的前提下提供最小用户认证能力，同时避免把 raw token、明文密码或服务端业务数据暴露给浏览器存储。

本变更只处理本地邮箱/密码认证和可撤销 opaque session。完整认证页面、密码重置、邮箱验证、角色权限、自动过期、刷新 token 和第三方身份提供商不在范围内。

## Goals / Non-Goals

**Goals：**

- 用 Alembic 新增规范化的 `users`、`auth_sessions` 表，并通过领域 record/Repository Protocol 隔离 ORM。
- 提供邮箱规范化、Argon2 密码哈希、统一凭据错误、dummy 校验和仅保存 SHA-256 token hash 的认证服务。
- 提供注册、登录、登出和当前用户 API，复用 P02 envelope/error/request ID，并通过显式数据库依赖运行。
- 扩展共享 TypeScript contracts、OpenAPI path 和 bearer security scheme，使后端与前端均由合同测试约束。
- 提供前端 authClient 与 Pinia auth state；localStorage 只保存 bearer token，认证失效或登出只清理本地受保护状态。

**Non-Goals：**

- 不实现自动 session 过期、刷新 token、并发 session 上限或后台清理任务。
- 不实现认证页面、密码重置、邮箱验证、角色/权限或第三方登录。
- 不删除服务端业务数据，也不把后端或前端放入 Compose。

## Decisions

### 1. 领域核心与 SQLite adapter 分离

`super_ai.auth` 只声明不可变 `UserRecord`、`AuthSessionRecord`、Repository Protocol、密码接口和 `AuthService`，不导入 SQLAlchemy。认证 ORM 与 repository adapter 位于 `super_ai.memory.extended_sqlite`，满足 P03 对可替换持久化实现的约束。Repository 输入输出只包含 record 或字符串 ID；修改、查询与撤销 session 时同时携带 `session_id` 和 `user_id`，避免跨 owner 更新。

替代方案是让 AuthService 直接接收 `AsyncSession` 或 ORM model；该方案会把 SQLite 细节扩散到领域层，故拒绝。

### 2. 规范化 schema 与唯一约束

`users` 包含 `id`、已规范化且唯一的 `email`、`password_hash`、`created_at`、`updated_at`。`auth_sessions` 包含 `id`、带外键的 `user_id`、唯一且长度为 64 的 `token_hash`、`created_at`、`last_seen_at`、可空 `revoked_at`。所有时间使用 UTC；当前 revision 不增加 `expires_at`，也不推断未实现的自动过期语义。

Alembic revision 是 schema 的唯一权威。应用启动只创建 engine/session runtime，不执行迁移或 `metadata.create_all`。

### 3. 邮箱、密码和凭据失败策略

邮箱在服务边界执行 `strip().casefold()`，数据库唯一约束承担最终竞态保护。密码由 `pwdlib[argon2]` 的推荐 Argon2 配置哈希；日志、错误 details、record 之外的响应与测试快照均不得包含明文密码。

用户不存在和密码错误都返回 `AUTH_INVALID_CREDENTIALS`。未知邮箱仍调用一次密码 verifier，并使用代码中预生成的有效 Argon2 dummy hash；dummy hash 不是凭据，且不得在 import 时动态计算。该设计降低明显的账号枚举和时序差异，但不声称提供严格恒定时间保证。

### 4. opaque token 只在边界返回一次

登录使用 `secrets.token_urlsafe(48)` 生成高熵 raw bearer token，客户端只在登录成功响应中取得该值。服务在持久化前执行 SHA-256，SQLite 只保存 64 位十六进制 `token_hash`。鉴权、更新 `last_seen_at` 和撤销都先对传入 token 做相同哈希；响应、日志和异常不得回显 token。

缺失、未知或已撤销 token 均使用现有 `AUTH_REQUIRED` 401 错误。成功鉴权更新 `last_seen_at`；登出把当前 owner 的 session 标记为撤销。当前版本只有显式撤销，没有自动过期。

### 5. FastAPI 依赖与生命周期

`create_app` 可接收显式 `DatabaseSettings`。传入配置时，lifespan 创建并关闭 P03 `PersistenceRuntime`；默认导入和 `create_app()` 不打开 SQLite。认证依赖从 runtime 取得每请求 session，组装 SQLite repository 和 AuthService。`HTTPBearer(auto_error=False, scheme_name="BearerAuth")` 提供机器可读 bearer scheme，业务依赖统一产生认证错误。

四个路由均复用 P02 success/error helper 与 request ID：注册返回用户，登录返回用户与 raw token，当前用户返回用户，登出返回 `{revoked:true}`。CORS 只新增 `http://127.0.0.1:5173` 本机桌面前端来源，并允许认证所需 headers/methods。

### 6. contracts 是 Auth HTTP 形状的单一事实来源

`packages/api-contracts` 新增 Auth DTO、请求/响应 data、认证错误和四个 path，manifest 新增 `BearerAuth` HTTP bearer scheme。受保护 path 显式引用该 scheme。后端不导入 TypeScript，但合同测试比较 Pydantic 序列化、错误目录、OpenAPI operationId/security 与共享 manifest。

### 7. 前端只持久化 token

authClient 复用 P02 ApiClient，不复制 envelope 或认证 payload。Pinia auth state 保存运行期 user/token/status；localStorage 只使用单一 token key，不保存 user、密码、session record 或完整响应。`initialize()` 在存在 token 时调用 `/auth/me`；401/`AUTH_REQUIRED` 表示凭据失效，随后移除 token、用户和注入的本地受保护 store。网络或系统错误保留 token，避免瞬时故障造成无意义登出。

logout 尝试调用服务端撤销；无论撤销成功还是服务端已判定 token 失效，前端都清理本地凭据与受保护 store。该清理回调不能发起服务端业务数据删除。P08 再实现完整页面。

## Risks / Trade-offs

- **Argon2 测试较慢** → 单元测试通过可注入密码接口覆盖 dummy 分支，集成测试保留真实 pwdlib 哈希验证。
- **SQLite 写并发有限** → 每请求独立 session、短事务和唯一约束满足当前本地边界；未来 PostgreSQL adapter 不改变领域 Protocol。
- **localStorage 可受 XSS 影响** → 当前产品明确采用 bearer/localStorage；前端不保存其他认证凭据，并继续使用 DOMPurify 等既定安全边界。未来若改为 cookie 必须单独提案。
- **没有自动过期** → UI/文档明确只支持显式撤销，避免虚构安全保证；过期与轮换策略由后续 change 设计。

## Migration Plan

1. 先扩展共享 contracts 与失败测试。
2. 新增 Alembic revision，并在 fresh 临时 SQLite 上升级到 head、比较 metadata。
3. 实现领域 record/Protocol、SQLite adapter、AuthService 与 API。
4. 实现前端 authClient/state，并验证恢复和清理。
5. 运行受影响门禁、OpenSpec verify、同步 delta specs 后归档。

回滚代码时可降级到上一 revision；生产数据删除不属于本变更，执行 destructive downgrade 前必须另行确认。

## Open Questions

无。自动过期、刷新 token 和完整页面均已明确延后。
