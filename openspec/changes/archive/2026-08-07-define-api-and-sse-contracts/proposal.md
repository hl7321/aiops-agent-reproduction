## Why

后续认证、聊天、AIOps 与 Agent 功能都会同时依赖 HTTP 和 SSE；如果各端分别定义临时 payload，错误语义、请求追踪与流式事件会快速漂移。现在需要先把机器可读合同、后端序列化和前端 transport 的共同边界固定下来，让后续提案只能扩展同一事实来源。

## What Changes

- 将 `packages/api-contracts` 建设为 HTTP envelope、稳定错误目录、OpenAPI path 和 SSE 判别联合的单一事实来源。
- 为 FastAPI 增加统一成功/失败响应、请求 ID 透传或生成、请求验证错误与未处理异常的安全转换。
- 将 `/health` 纳入机器可读 OpenAPI 合同，并改为返回统一成功 envelope。
- 为前端增加 typed `apiClient` 和 `sseClient` 基础，支持 envelope 解包、认证与请求 ID 扩展点，以及跨 chunk SSE frame 解析。
- 增加跨语言合同测试，证明 Pydantic/JSON 序列化与 TypeScript 合同一致，并禁止前后端自造临时事件结构。
- 不实现认证、聊天、知识库、AIOps、Agent、LLM、Milvus 或 MCP 产品行为。

## Capabilities

### New Capabilities

- `api-and-sse-contracts`: 统一定义 HTTP envelope、错误目录、OpenAPI path、SSE 事件目录以及前后端 transport 合同。

### Modified Capabilities

- `monorepo-foundation`: 将 foundation `/health` 响应改为带 request ID 的统一成功 envelope，并要求其路径来自共享 OpenAPI 合同。

## Impact

- `packages/api-contracts`：新增共享类型、错误目录、OpenAPI path、SSE 事件与合同测试。
- `apps/backend`：新增 Pydantic 合同模型、响应 helper、中间件和异常处理，并调整 `/health`。
- `apps/frontend`：新增 typed HTTP/SSE transport 与测试。
- `tests`：新增跨语言形状、事件目录和禁止私有 payload 的仓库策略测试。
- 不新增外部基础设施、应用容器或产品 endpoint；现有依赖边界保持不变。
