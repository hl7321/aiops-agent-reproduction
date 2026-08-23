# API Contracts

本 workspace 是 HTTP envelope、稳定错误目录、OpenAPI path、Auth DTO 和 SSE 事件的单一事实来源。公开类型统一从 `@super-ai/api-contracts` entrypoint 导入；`contract-manifest.json` 为 Python 合同测试提供机器可读目录。

当前登记完整认证、Chat、Knowledge、MCP、AIOps、Feedback 与运行时探针路径、`BearerAuth` scheme，并提供八种共享 SSE event 形状。后续 change 必须先扩展 manifest、typed entrypoint 和合同测试，再增加后端 endpoint 或事件生产者；自动化合同测试证明形状一致，不代表真实外部 provider 连通。

`protectedPathPolicy` 规定所有受保护 path 必须复用 `BearerAuth`、`AUTH_REQUIRED` 401 与 `AUTH_FORBIDDEN` 403；直接资源不可见统一使用 `BUSINESS_RESOURCE_NOT_FOUND` 404。

```bash
npm run typecheck
npm run test
```
