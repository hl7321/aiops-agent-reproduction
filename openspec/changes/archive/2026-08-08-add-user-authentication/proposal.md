## Why

后续 Chat、知识、任务和审计都需要稳定的用户身份与可撤销会话；如果各功能自行处理密码、token 或恢复状态，会破坏 P02 的共享合同和 P03 的持久化边界。因此本阶段先实现最小、可测试且不泄露凭据的本地用户认证能力。

## What Changes

- 新增 `users` 与 `auth_sessions` 规范化表及 Alembic migration，邮箱规范化后唯一。
- 使用 `pwdlib[argon2]` 保存密码哈希；登录使用高熵 opaque bearer token，数据库只保存 64 位 SHA-256 token hash。
- 新增 owner-safe Repository、AuthService、dummy Argon2 验证和 FastAPI 认证 dependency。
- 提供注册、登录、登出、当前用户与认证恢复所需的四个 HTTP API，全部复用统一 envelope、错误目录和 request ID。
- 扩展共享 contracts 的 Auth DTO、请求/响应、bearer security scheme、认证错误和 OpenAPI path 目录。
- 前端新增可复用 authClient 与 Pinia auth state；localStorage 只保存 bearer token，恢复失败或登出时只清理本地受保护状态。
- 允许桌面本机前端来源 `http://127.0.0.1:5173` 访问后端。
- 明确本版本不实现自动 session 过期、完整认证页面、密码重置、邮箱验证、角色权限或服务端业务数据删除。

## Capabilities

### New Capabilities

- `user-authentication`: 定义本地用户注册、登录、可撤销 bearer session、当前用户、认证恢复和前端凭据清理行为。

### Modified Capabilities

- `api-and-sse-contracts`: 扩展 Auth DTO、认证错误、bearer security scheme 与四个认证 OpenAPI paths，并要求后端/前端直接消费这些合同。

## Impact

- 后端新增 auth 领域、SQLite adapter、Pydantic DTO、FastAPI router/dependencies、CORS 和第二个 Alembic revision。
- 后端新增 `pwdlib[argon2]` 运行时依赖，并更新 `uv.lock`。
- `packages/api-contracts` 增加认证类型与机器可读 manifest；前端新增 transport/state 与测试，但不新增完整页面。
- 现有 `/health`、HTTP/SSE envelope、P03 migration/runtime 行为保持兼容。
