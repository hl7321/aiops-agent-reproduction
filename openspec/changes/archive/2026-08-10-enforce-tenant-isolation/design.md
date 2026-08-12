## Context

P04 已提供 `AuthPrincipal`、可撤销 bearer session 与异步 SQLite Repository adapter，但业务资源尚未落地。P05 在第一张业务表出现前建立 tenant/owner 边界，因此不需要迁移现有业务数据，也不应创造临时 Chat、Knowledge 或 Vector 表。参见 proposal.md 与本 change 的四份 delta specs。

## Goals / Non-Goals

**Goals：**

- 把认证 user id 显式转换成不可变 CurrentUser、OwnerScope 和 TenantContext。
- 提供能直接复用于未来 ORM model 的 SQLite scoped select/update/delete/parent-child builder，并用两个用户的真实 SQLite 合同测试证明隔离。
- 通过 Protocol、运行期签名验证器和仓库治理测试强制 `owner_user_id` 参数。
- 统一直接资源 404 与受保护父资源 403 的不可枚举语义。
- 用纯函数锁定 Milvus metadata/search/delete filter，不创建 client 或连接外部服务。
- 扩展共享 contracts 与 FastAPI OpenAPI，使受保护 path 复用 bearer、401、403。

**Non-Goals：**

- 不创建产品资源表、Alembic revision、Chat/Knowledge CRUD、真实 Milvus client 或 retrieval tool。
- 不实现组织、多成员 tenant、角色授权或 tenant 切换；当前 tenant 永远等于当前 user。
- 不修改 logout 的既有撤销行为，也不增加级联业务数据删除。

## Decisions

### 1. CurrentUser、OwnerScope 与 TenantContext 分层表达同一身份

`CurrentUser` 由认证 dependency 从 `AuthPrincipal.user.id` 创建；`OwnerScope` 保存 `owner_user_id`，`TenantContext` 同时保存 `current_user` 和 scope，并暴露 `tenant_id`。构造器拒绝空值；当前版本只允许 tenant、owner、user 三者相等。向量 metadata 仍同时写 `tenantId` 与 `ownerUserId`，为未来组织 tenant 与归属审计分离保留兼容字段。

替代方案是只传裸 `user_id`；它无法区分“调用身份”“数据 owner”“检索 tenant”三种语义，未来容易把不可信参数当作 scope，因此拒绝。

### 2. owner scope 必须进入同一 SQL 语句

`super_ai.tenancy.repositories` 声明 owner-scoped Protocol；每个受保护方法的第一个业务参数固定命名为 `owner_user_id`。`super_ai.memory.sqlite.owner_scope` 提供 scoped select/update/delete 与 parent-child condition builder，组合 `owner_column == owner_user_id` 和资源/父标识。helper 在构造 SQL 前拒绝空 owner。

合同测试使用测试专用 SQLAlchemy Base 与临时 SQLite，创建两个 owner 但相同可猜测资源 ID 的记录，直接执行 helper 生成的语句。测试专用表不进入产品 metadata，P05 不新增迁移。

替代方案是 repository `get(id)` 后由 service 比较 record.owner；该方案已经在需求中明确禁止，因为它把其他用户数据加载到进程并容易遗漏检查。

### 3. 错误语义不依赖无 scope 存在性探测

scoped direct read 返回 None 时统一转换为 `BUSINESS_RESOURCE_NOT_FOUND` 404；无论 ID 不存在还是属于其他 owner，响应相同。父资源入口使用更保守的统一 `AUTH_FORBIDDEN` 403：scoped parent 不可见时，不执行第二次无 scope 查询，因此不存在和越权保持相同结果。错误 helper 只接收 scoped 查询结果，不接收 ORM。

### 4. 受保护 OpenAPI policy 是机器可读合同

manifest 增加 `protectedPathPolicy`，声明 `BearerAuth`、`AUTH_REQUIRED`、`AUTH_FORBIDDEN`。每个 path 可列出 `errors`；合同测试要求一旦 path 使用 `BearerAuth`，就必须包含 policy 的 401/403。FastAPI 受保护路由显式登记统一 FailureEnvelope responses，后端测试直接与 manifest 对比。

### 5. Milvus scope builder 保持纯函数且默认拒绝

`VectorScope` 从 TenantContext 和允许 KB IDs 创建。搜索 filter 只输出 `tenantId == ... and knowledgeBaseId in [...]`，使用 JSON 字符串编码避免 filter 注入；不会接受 document/metadata 条件。空 KB 列表返回 None，异步执行 wrapper 在调用 client factory/search callback 前直接返回空列表。

召回后 filter 接受已经 scoped 的 hits，再按 document IDs 或 metadata predicate 缩小结果。metadata builder 先拒绝额外字段覆盖，再写入 tenant、owner、KB、document。delete builder 要求 tenant、KB、document 全部非空，并输出三条件 AND；不存在宽删除 fallback。

替代方案是把所有可选条件拼入 Milvus filter；这会混淆授权 scope 与业务过滤，并增加未来动态 metadata 的注入/兼容风险，因此延后到 retrieval tool 的召回后阶段。

### 6. 登出与数据生命周期保持正交

后端 logout 继续只撤销 `auth_sessions`；前端继续只移除 token、用户和本地受保护 store。集成测试在登出前后查询持久用户 record，并用新 session 重新认证，证明数据生命周期不依赖认证 session。

## Risks / Trade-offs

- **父资源不存在也返回 403，语义比 404 更保守** → 避免为了区分存在性而执行不安全查询，并在合同中明确该规则。
- **运行期签名验证器需要未来 adapter 主动采用 marker** → 同时增加 AST 仓库治理测试和 AGENTS 规则，CI 对新受保护 Repository 执行参数检查。
- **filter 是字符串合同** → 使用 JSON quoting、非空验证与精确字面量测试；真实 pymilvus 集成由后续向量 change 负责。
- **当前 tenant=user 限制组织场景** → 保留 tenant/owner 双字段，未来组织模型通过新 OpenSpec change 扩展，不静默改变现有语义。

## Migration Plan

1. 先扩展 contracts 与失败测试，不修改产品 schema。
2. 增加 tenancy value objects、Repository 治理和 SQLite helper，运行双用户合同测试。
3. 增加纯向量 scope/filter builder 与空 scope 短路测试。
4. 更新 FastAPI OpenAPI、logout 持久性测试、AGENTS 与架构说明。
5. 完整门禁、verify、delta spec sync 后归档。

P05 不产生数据库迁移，回滚只需移除新 helper/contracts；已存在用户和 session 数据不变。
