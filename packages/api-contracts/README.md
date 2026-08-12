# API Contracts

本 workspace 是 HTTP envelope、稳定错误目录、OpenAPI path、Auth DTO 和 SSE 事件的单一事实来源。公开类型统一从 `@super-ai/api-contracts` entrypoint 导入；`contract-manifest.json` 为 Python 合同测试提供机器可读目录。

当前登记 foundation `/health`、四个认证 endpoint、`BearerAuth` scheme，并提供八种基础 SSE event 形状。聊天、AIOps 和实际流式 endpoint 尚未实现。后续 change 必须先扩展 manifest、typed entrypoint 和合同测试，再增加后端 endpoint 或事件生产者。

`protectedPathPolicy` 规定所有受保护 path 必须复用 `BearerAuth`、`AUTH_REQUIRED` 401 与 `AUTH_FORBIDDEN` 403；直接资源不可见统一使用 `BUSINESS_RESOURCE_NOT_FOUND` 404。

```bash
npm run typecheck
npm run test
```
