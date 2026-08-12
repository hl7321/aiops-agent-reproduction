## MODIFIED Requirements

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
