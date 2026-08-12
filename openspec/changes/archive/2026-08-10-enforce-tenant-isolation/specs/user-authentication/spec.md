## MODIFIED Requirements

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

### Requirement: 前端认证恢复只持久化 bearer token
前端 SHALL 提供直接消费共享 Auth DTO 的 typed authClient 与 Pinia auth state。bearer token MUST 是 localStorage 中唯一认证凭据；用户、密码、完整响应和服务端 session MUST NOT 写入 localStorage。存在 token 时 `initialize()` SHALL 调用 `/auth/me`；凭据失效或 logout SHALL 清除 token、用户和本地受保护 store，但 MUST NOT 删除服务端用户或业务持久数据。后端 logout MUST 只撤销认证 session，不得触发资源级删除。

#### Scenario: 从有效 token 恢复认证
- **WHEN** localStorage 已有 token 且 `/auth/me` 成功
- **THEN** auth state 恢复共享用户 DTO，且 localStorage 没有新增其他认证字段

#### Scenario: 失效 token 清理本地状态
- **WHEN** `/auth/me` 返回共享 401 认证错误
- **THEN** 前端移除 token、用户和本地受保护 store，并且不调用服务端数据删除 API

#### Scenario: 登出清理本地状态
- **WHEN** 用户触发 logout
- **THEN** 前端请求服务端撤销当前 session，随后只清理本地认证与受保护状态

#### Scenario: 登出保留持久数据
- **WHEN** 用户在拥有持久数据时成功登出
- **THEN** session 被撤销但用户与其持久数据仍可由同 owner 的后续认证 session 访问
