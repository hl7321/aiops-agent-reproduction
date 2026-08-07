# API Contracts

本 workspace 是 HTTP envelope、稳定错误目录、OpenAPI path 和 SSE 事件的单一事实来源。公开类型统一从 `@super-ai/api-contracts` entrypoint 导入；`contract-manifest.json` 为 Python 合同测试提供机器可读目录。

当前只登记 foundation `/health`，并提供八种基础 SSE event 形状；认证、聊天、AIOps 或实际流式 endpoint 尚未实现。后续 change 必须先扩展 manifest、typed entrypoint 和合同测试，再增加后端 endpoint 或事件生产者。

```bash
npm run typecheck
npm run test
```
