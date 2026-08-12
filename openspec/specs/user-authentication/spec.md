# 用户认证规格

## Purpose

本能力定义最小、安全且可撤销的本地用户认证边界，使后续业务能够取得稳定用户身份，同时不泄露密码、raw bearer token 或服务端业务数据。

## Requirements

### Requirement: 认证 schema 由 Alembic 和 owner-safe Repository 管理
系统 MUST 通过 Alembic 新增规范化 `users` 与 `auth_sessions` 表。领域服务 SHALL 只依赖不可变 record 与 Repository Protocol，不得接收 ORM model 或 `AsyncSession`；SQLite adapter MUST 位于 `super_ai.memory.sqlite` 或 `super_ai.memory.extended_sqlite`。session 查询、更新和撤销 MUST 绑定所属 `user_id` 与 `session_id`。

#### Scenario: fresh 数据库升级认证 schema
- **WHEN** 临时 SQLite 数据库从零执行 `alembic upgrade head`
- **THEN** `users` 与 `auth_sessions` 表、唯一约束、外键和时间字段均存在，且 metadata 与迁移 schema 一致

#### Scenario: owner-safe session 更新
- **WHEN** repository 使用不匹配的 `user_id` 更新或撤销一个 session
- **THEN** 该 session 不被修改且调用方无法观察到其他 owner 的 ORM 数据

### Requirement: 注册规范化邮箱并只保存 Argon2 哈希
注册 SHALL 对邮箱执行去除首尾空白和不区分大小写的规范化，并在数据库中保证规范化邮箱唯一。密码 MUST 使用 `pwdlib[argon2]` 哈希，明文密码 MUST NOT 保存、记录或返回。

#### Scenario: 注册新用户
- **WHEN** 客户端提交有效邮箱和密码
- **THEN** 系统保存规范化邮箱与 Argon2 password hash，并返回不含 password/hash 的用户 DTO

#### Scenario: 重复邮箱注册
- **WHEN** 两次注册的邮箱仅大小写或首尾空白不同
- **THEN** 第二次请求返回登记的重复邮箱错误，且数据库只存在一个用户

### Requirement: 登录统一凭据错误并隐藏账号存在性
登录 SHALL 对已知用户校验其 Argon2 hash，对未知邮箱也 MUST 对预生成的有效 dummy Argon2 hash 执行一次校验。用户不存在与密码错误 MUST 返回同一个 `AUTH_INVALID_CREDENTIALS` code、HTTP status 和安全消息。

#### Scenario: 使用正确密码登录
- **WHEN** 已注册用户提交规范化后匹配的邮箱和正确密码
- **THEN** 登录成功并创建新的 auth session

#### Scenario: 使用错误密码登录
- **WHEN** 已注册用户提交错误密码
- **THEN** 返回 `AUTH_INVALID_CREDENTIALS` 且不创建 session

#### Scenario: 使用未知邮箱登录
- **WHEN** 未注册邮箱尝试登录
- **THEN** 系统仍执行 dummy Argon2 校验并返回与错误密码完全相同的 `AUTH_INVALID_CREDENTIALS` 响应

### Requirement: bearer session 只持久化 token hash
登录 SHALL 使用密码学安全随机源生成高熵 opaque bearer token，客户端获得 raw token，SQLite MUST 只保存其 64 位十六进制 SHA-256 hash。session MUST 保存 `createdAt`、`lastSeenAt` 与可空 `revokedAt`；成功鉴权 SHALL 更新 `lastSeenAt`，并将认证用户映射为 CurrentUser，其 `tenant_id` 与 `owner_user_id` 均等于 user id；登出 SHALL 只撤销当前 session。当前版本 MUST NOT 声称或实现自动过期策略。

#### Scenario: 数据库不包含 raw token
- **WHEN** 登录成功后检查响应和数据库 session
- **THEN** 响应包含 raw token，数据库只包含等于该 token SHA-256 值的 64 位 hash

#### Scenario: 当前用户鉴权更新 lastSeen
- **WHEN** 活跃 bearer token 调用当前用户接口
- **THEN** 返回其 owner 用户且该 session 的 `lastSeenAt` 不早于鉴权前的值

#### Scenario: 登出撤销 session
- **WHEN** 活跃 bearer token 调用登出后再次请求受保护接口
- **THEN** session 具有 `revokedAt`，后续请求返回统一 401 认证错误

#### Scenario: 认证用户产生 tenant context
- **WHEN** bearer dependency 成功恢复当前用户
- **THEN** CurrentUser 的 user、tenant 与 owner 标识均非空且指向同一用户

### Requirement: 认证 API 复用统一 HTTP 边界
后端 SHALL 提供 `POST /auth/register`、`POST /auth/login`、`POST /auth/logout` 与 `GET /auth/me`。所有响应 MUST 使用共享 envelope/error/request ID；受保护接口 MUST 使用 bearer dependency。CORS SHALL 允许 `http://127.0.0.1:5173` 携带认证所需 method 和 header。

#### Scenario: 四个 API 返回共享 envelope
- **WHEN** 客户端依次注册、登录、查询当前用户和登出
- **THEN** 每个响应均具有共享 envelope 与一致 request ID，且受保护接口要求 bearer token

#### Scenario: 本机前端执行 CORS 预检
- **WHEN** `http://127.0.0.1:5173` 为认证请求发送合法 OPTIONS 预检
- **THEN** 后端返回允许该 origin、method 和 Authorization header 的 CORS 响应

### Requirement: 前端认证恢复只持久化 bearer token
前端 SHALL 提供直接消费共享 Auth DTO 的 typed authClient 与 Pinia auth state。bearer token MUST 是 localStorage 中唯一认证凭据；用户、密码、完整响应和服务端 session，以及 Chat、知识库和 AIOps 领域数据 MUST NOT 写入 localStorage。首次路由导航 MUST 至多启动一次 `initialize()`；存在 token 时 `initialize()` SHALL 调用 `/auth/me`。凭据失效、typed transport 收到共享 401 或 logout SHALL 清除 token、用户和所有已注册本地受保护 store，但 MUST NOT 删除服务端用户或业务持久数据。后端 logout MUST 只撤销认证 session，不得触发资源级删除。

#### Scenario: 从有效 token 恢复认证
- **WHEN** localStorage 已有 token 且首次路由导航触发 `/auth/me` 成功
- **THEN** auth state 恢复共享用户 DTO，工作台按原目标继续导航，且 localStorage 没有新增其他认证或领域字段

#### Scenario: 失效 token 清理本地状态
- **WHEN** `/auth/me` 或其他 typed API 请求返回共享 401 认证错误
- **THEN** 前端移除 token、用户和所有已注册本地受保护 store，并且不调用服务端数据删除 API

#### Scenario: 登出清理本地状态
- **WHEN** 用户触发 logout
- **THEN** 前端先请求服务端撤销当前 session，随后无论请求成功与否都清理本地认证与受保护状态

#### Scenario: 登出保留持久数据
- **WHEN** 用户在拥有持久数据时成功登出
- **THEN** session 被撤销但用户与其持久数据仍可由同 owner 的后续认证 session 访问

#### Scenario: 同一应用实例只恢复一次
- **WHEN** 应用在首次认证恢复后继续发生路由导航
- **THEN** 前端不重复调用 `/auth/me` 且使用当前 auth state 完成路由判断
