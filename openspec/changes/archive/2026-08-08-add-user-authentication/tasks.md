## 1. 共享合同先行

- [x] 1.1 先为 Auth DTO、请求/响应 data、认证错误、BearerAuth scheme 和四个 OpenAPI path 编写失败的 contracts 测试
- [x] 1.2 实现共享 Auth contracts 与 manifest 扩展，使 contracts typecheck/test 通过
- [x] 1.3 增加后端合同测试，约束 Auth Pydantic 形状、错误目录、operationId 和 security 与 TypeScript manifest 一致

## 2. 认证持久化边界

- [x] 2.1 先编写 fresh migration、schema/metadata、hash 非明文、数据库无 raw token 和 owner-safe Repository 的失败测试
- [x] 2.2 新增不可变用户/session record、Repository Protocol 与 `pwdlib[argon2]` 依赖
- [x] 2.3 新增 users/auth_sessions ORM、SQLite repository adapter 和 Alembic revision，使 migration/repository 测试通过
- [x] 2.4 验证导入 auth/memory 模块不会创建 engine、SQLite 文件、密码 hash 或执行迁移

## 3. AuthService 与 HTTP API

- [x] 3.1 先编写注册、邮箱规范化/重复、正确/错误/未知登录、dummy Argon2、token hash、lastSeen 和撤销的失败测试
- [x] 3.2 实现密码接口、token 原语、AuthService 和统一认证领域错误，使服务测试通过
- [x] 3.3 先编写四个 API、统一 envelope/error/request ID、401、恢复、登出和 CORS 的失败测试
- [x] 3.4 实现 FastAPI auth DTO/router/dependencies、显式 persistence lifespan 与本机前端 CORS，使 API 测试通过

## 4. 前端认证基础

- [x] 4.1 先编写 authClient 请求/解包、token-only storage、initialize 恢复/失效清理和 logout 清理的失败测试
- [x] 4.2 实现直接消费共享合同的 authClient 与可注入依赖的 Pinia auth state，不新增完整认证页面
- [x] 4.3 增加仓库策略测试，阻止私有 Auth payload、明文密码记录和 localStorage 额外认证凭据

## 5. 验证与完成

- [x] 5.1 运行并修复 backend 的 migration、pytest、Ruff 与 strict Pyright 门禁
- [x] 5.2 运行并修复 contracts typecheck/test 与 frontend typecheck/test/build 门禁
- [x] 5.3 运行 `openspec validate --all`、`git diff --check` 和 `$openspec-verify-change`，修复全部 CRITICAL 并处理 WARNING
- [x] 5.4 确认 delta specs 可同步、所有任务完成且 change 满足归档条件
