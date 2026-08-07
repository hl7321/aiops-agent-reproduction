## Context

参见 `proposal.md` 的动机。当前 contracts 只有 `FoundationStatus`，后端 `/health` 返回裸对象，前端没有 HTTP/SSE transport。P02 需要同时约束 TypeScript、FastAPI/Pydantic 与前端消费端，但不能让后端在运行时依赖 TypeScript，也不能提前实现任何产品 endpoint。

本设计继续使用 Python >=3.10、FastAPI、Pydantic v2、pytest、Ruff、strict Pyright，以及 Vue 3.5、TypeScript 5.6 strict、Vitest 2 和 Vite 6。所有新模块保持 import safety，不在导入时连接数据库、LLM、Milvus 或 MCP；配置公开边界和依赖注入规则不变。

## Goals / Non-Goals

**Goals:**

- 让 `packages/api-contracts` 成为 HTTP、错误、OpenAPI path 与 SSE 的规范入口。
- 用稳定、可判别、可扩展的类型边界支持后续 change。
- 让 FastAPI 的成功、已知失败、验证失败和系统失败具有同一响应形状与 request ID。
- 让前端 transport 只消费共享合同，并正确处理真实网络 chunk 边界。
- 用跨语言合同测试证明 Python 镜像模型与合同事实一致。

**Non-Goals:**

- 不生成完整 OpenAPI client/server，也不引入代码生成工具链。
- 不实现认证、聊天、AIOps、知识库、Agent 或任何实际 SSE endpoint。
- 不定义业务专属 report、reference 或 task 内容；本阶段只固定可扩展的基础字段。
- 不读取 OS 环境变量，也不改变现有 public-config allowlist。

## Decisions

### 1. 合同包按职责拆分，并提供统一 typed entrypoint

`packages/api-contracts/src` 分为 `http.ts`、`errors.ts`、`openapi.ts`、`sse.ts` 和 `index.ts`。`index.ts` 是唯一公开 entrypoint；前端只从 `@super-ai/api-contracts` 导入，不引用子路径。合同包同时保存机器可读 `contract-manifest.json`，记录错误目录、OpenAPI path、SSE type 与 tool lifecycle；TypeScript 测试保证 manifest 与导出常量一致，Python 测试读取 manifest 比较自身模型。

备选方案一是只维护 TypeScript 常量并让 Python 测试解析源码，容易受格式影响；备选方案二是立即引入 OpenAPI/JSON Schema 代码生成，会增加新工具链和生成物维护成本。选择小型 manifest 加 typed 模块，在 P02 保持透明且可测试，后续可无破坏地接入生成器。

### 2. HTTP envelope 使用泛型 TypeScript 与 Pydantic 模型镜像

共享类型定义 `SuccessEnvelope<T>`、`FailureEnvelope`、`ApiEnvelope<T>`、`ApiError` 和 `RequestMeta`。后端以 Pydantic v2 泛型模型镜像同一 JSON 形状，所有 JSON 使用 camelCase alias。响应 helper 只接受已登记错误定义或完整 `ApiError`，endpoint 不直接拼装字典。

备选方案是依赖 FastAPI 默认错误响应，但其 validation detail 与业务错误形状不同，也无法统一 request ID，因此不采用。

### 3. 错误目录是数据，不把内部异常消息当作合同

初始目录提供 `AUTH_REQUIRED`、`AUTH_FORBIDDEN`、`BUSINESS_RULE_VIOLATION`、`VALIDATION_REQUEST_INVALID` 和 `SYSTEM_INTERNAL_ERROR`。错误定义包含 category、httpStatus、defaultMessage。应用错误携带可选安全 details；未处理异常固定映射到 `SYSTEM_INTERNAL_ERROR`，日志/内部文本不进入响应。验证错误 details 只保留规范化字段路径、错误类型与安全消息。

备选方案是允许 endpoint 传任意 code，扩展速度快但无法形成稳定目录；因此禁止。

### 4. request ID 由 HTTP 中间件建立单请求上下文

中间件接受长度 1–128 且只含字母、数字、点、下划线、冒号或连字符的 `X-Request-ID`；无效或缺失时生成 UUID。值写入 `request.state`，供 endpoint 与 exception handler 共用，并最终写回响应 header。这样四类响应不会生成不同 ID，也不需要全局可变状态。

备选方案是使用模块级全局变量，异步并发下会串请求；使用 `ContextVar` 也可行，但当前 handler 已获得 `Request`，`request.state` 更直接。

### 5. SSE 事件采用扁平公共字段加 typed data

每个事件固定 `id`、`type`、`channel`、`timestamp`，事件专属内容放在 `data`。`tool.call.data.lifecycle` 是 `started | delta | completed | failed`，并固定 `toolCallId`；`error.data.error` 直接使用 `ApiError`。基础 payload 使用 JSON value 或最小标识字段，后续提案通过增加可选字段或新增共享事件扩展，不在功能模块中复制 union。

备选方案是把 type 放在 SSE wire 的 `event:` 行、JSON 仅放 payload。那会让普通 JSON 日志和重放记录失去自描述性，因此仍把 `type` 放在 JSON 事件内；parser 可忽略 wire event 名并以 JSON 判别。

### 6. 前端 transport 使用可注入 fetch 与流式增量 parser

`createApiClient` 和 `createSseClient` 接受 fetch、bearer token provider、request ID provider 扩展点，默认不读取任何私密配置。HTTP client 返回 `{data, requestId}`，失败时抛出携带 `ApiError` 与 request ID 的 typed error。SSE parser 持有字符串 buffer，以空行识别 frame，合并多个 `data:` 行，支持 CRLF、一个 chunk 多 frame 与一个 frame 多 chunk；client 用 `TextDecoder` 的 streaming 模式驱动 parser。

备选方案是按 chunk 直接 `JSON.parse`，无法处理浏览器流边界，因此不采用。备选 EventSource 不支持自定义 Authorization header，也不适合作为 bearer 扩展基础。

### 7. OpenAPI path 采用共享目录并由 FastAPI 测试反向校验

合同 manifest/模块登记 `/health`、GET、`getHealth` 与成功数据合同名。FastAPI route 显式使用相同 operationId；测试读取 `app.openapi()` 比较路径和 operationId。后续 endpoint 的 change 必须先修改该目录及测试，再添加 route。

本阶段不维护一份手写完整 OpenAPI document，避免与 FastAPI 自动 schema 双重漂移；共享目录负责治理 path，FastAPI 仍负责输出完整 OpenAPI。

## Risks / Trade-offs

- [风险] TypeScript 与 Python 仍有手写镜像类型 → 使用 manifest、序列化样例与 OpenAPI 测试逐项比较，任何新增目录项必须先让测试失败。
- [风险] SSE parser 不是完整 WHATWG EventSource 实现 → 明确只支持本项目需要的 `data`、`id`、注释与 frame 边界；重连策略和 retry 字段留给实际 SSE endpoint change。
- [风险] 通用 JSON payload 可能让未来类型过宽 → 本阶段只为未知产品内容保留 JSON value；后续功能必须在共享合同内收窄对应事件 data。
- [风险] BaseHTTPMiddleware/函数中间件会包裹异常路径 → 使用真实 ASGI 请求覆盖验证异常、应用异常和未处理异常，并验证同一 request ID。
- [风险] `details` 可能泄露内部信息 → helper 只接受调用方明确标记的安全 details，系统异常从不转发原异常内容。

## Migration Plan

1. 先扩展 contracts 与测试，使旧后端和缺失 transport 的测试失败。
2. 增加后端模型、helper、中间件和 handler，再迁移 `/health` 到 envelope。
3. 增加前端 transport 和跨 chunk parser。
4. 运行跨语言治理测试和全部门禁。
5. 本变更只修改 foundation `/health`；如需回滚，可恢复旧 health 响应并回退相同 change，不涉及持久化数据迁移。
