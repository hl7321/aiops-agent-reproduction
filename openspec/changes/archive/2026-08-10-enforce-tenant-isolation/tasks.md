## 1. 共享合同与受保护 path policy

- [x] 1.1 先为 `BUSINESS_RESOURCE_NOT_FOUND`、protectedPathPolicy、BearerAuth 及 401/403 path errors 编写失败的 contracts 测试
- [x] 1.2 实现共享错误和机器可读受保护 path policy，使 contracts typecheck/test 通过
- [x] 1.3 增加后端 OpenAPI 直接对比 manifest 的失败测试，并为现有受保护路由登记共享 401/403 responses

## 2. CurrentUser 与 owner-scoped Repository

- [x] 2.1 先为 CurrentUser、OwnerScope、TenantContext 的相等/非空约束编写失败测试
- [x] 2.2 实现不可变 tenant value objects 和 FastAPI CurrentUser/TenantContext dependency
- [x] 2.3 先为受保护 Repository 的 `owner_user_id` 参数级治理编写失败测试
- [x] 2.4 实现 owner-scoped Protocol、签名验证器与仓库治理检查

## 3. SQLite 双用户隔离与错误语义

- [x] 3.1 先用测试专用 ORM 和临时 SQLite 编写双用户 read/update/delete/父子资源失败测试
- [x] 3.2 实现 SQLite scoped select/update/delete/parent-child helper，禁止空 owner scope
- [x] 3.3 实现 scoped resource/parent 错误映射，并验证直接资源 404 不可枚举与父资源统一 403

## 4. 向量 tenant scope 合同

- [x] 4.1 先为 tenant/owner metadata、搜索 filter、空 KB 短路、召回后 filter 和 delete filter 编写失败测试
- [x] 4.2 实现纯函数 VectorScope、metadata/search/delete filter builder 与无连接短路执行器
- [x] 4.3 验证可选 document/metadata filter 只缩小已 scoped 召回结果且受保护 metadata 不可覆盖

## 5. Logout、文档与治理

- [x] 5.1 增加登出后用户持久数据保留及新 session 可恢复访问的集成测试
- [x] 5.2 更新 AGENTS、README 与 tenant isolation 架构文档，覆盖所有指定后续领域
- [x] 5.3 验证 tenancy 模块 import-safe 且未新增产品表、Alembic revision或外部连接

## 6. 验证与归档准备

- [x] 6.1 运行并修复 backend pytest/Ruff/strict Pyright 与 contracts/frontend 相关门禁
- [x] 6.2 运行 `openspec validate --all`、`git diff --check` 和 `$openspec-verify-change`，修复全部 CRITICAL/WARNING
- [x] 6.3 确认所有 delta specs 可同步且 change 满足归档条件
