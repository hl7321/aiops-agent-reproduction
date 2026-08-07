# API 与 SSE 合同实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立以 `packages/api-contracts` 为单一事实来源的 HTTP envelope、错误目录、OpenAPI path、SSE 判别联合，以及与之对齐的 FastAPI 和前端 transport。

**Architecture:** contracts 包通过机器可读 manifest 和统一 TypeScript entrypoint发布合同；Python 使用 Pydantic v2 镜像模型并由测试读取 manifest 做跨语言比对。FastAPI 中间件建立 request ID，统一 helper/handler 生成 envelope；前端可注入 fetch/token/request ID，并使用有状态 parser 处理跨 chunk SSE frame。

**Tech Stack:** TypeScript 5.6 strict、Vitest 2、Vue/Vite 6；Python >=3.10、FastAPI、Pydantic v2、pytest、Ruff、strict Pyright；OpenSpec spec-driven。

## Global Constraints

- 成功 envelope 固定为 `{ok:true,data,meta:{requestId}}`。
- 失败 envelope 固定为 `{ok:false,error:{code,category,httpStatus,message,details?},meta:{requestId}}`。
- SSE type 固定包含 `content.delta`、`reasoning.delta`、`tool.call`、`reference.source`、`task.status`、`report`、`complete`、`error`。
- tool lifecycle 固定为 `started | delta | completed | failed`；SSE error 复用 HTTP `ApiError`。
- 后端只使用 `from super_ai...`，模块导入期间无 I/O。
- 前端只从 `@super-ai/api-contracts` entrypoint 导入合同，不复制事件联合。
- 不实现认证、聊天、知识库、AIOps、Agent、LLM、Milvus 或 MCP 产品功能。
- 当前 foundation 尚未整体提交，本计划不创建独立 worktree，也不执行 Git commit。

---

### Task 1: 建立共享合同

**Files:**
- Create: `packages/api-contracts/contract-manifest.json`
- Create: `packages/api-contracts/src/http.ts`
- Create: `packages/api-contracts/src/errors.ts`
- Create: `packages/api-contracts/src/openapi.ts`
- Create: `packages/api-contracts/src/sse.ts`
- Modify: `packages/api-contracts/src/index.ts`
- Modify: `packages/api-contracts/src/index.test.ts`

**Interfaces:**
- Produces: `SuccessEnvelope<T>`、`FailureEnvelope`、`ApiEnvelope<T>`、`ApiError`、`ERROR_DEFINITIONS`、`OPENAPI_PATHS`、`SSE_EVENT_TYPES`、`TOOL_CALL_LIFECYCLES`、`SseEvent`。
- Consumers: FastAPI 镜像测试与 frontend transport。

- [ ] **Step 1: 写失败测试**

使用手写 fixture 覆盖成功、AUTH/BUSINESS、VALIDATION、SYSTEM 四类响应语义；断言五个初始错误定义、`/health` GET/getHealth、八种事件、四种 lifecycle，以及 `ErrorEvent["data"]["error"]` 可赋值为 `ApiError`。

- [ ] **Step 2: 验证 RED**

Run: `npm run contracts:test`

Expected: 因 `ERROR_DEFINITIONS`、`OPENAPI_PATHS` 或 SSE 导出缺失而失败。

- [ ] **Step 3: 实现最小合同**

核心形状：

```ts
export interface SuccessEnvelope<T> { ok: true; data: T; meta: { requestId: string } }
export interface ApiError { code: ErrorCode; category: ErrorCategory; httpStatus: number; message: string; details?: JsonValue }
export interface FailureEnvelope { ok: false; error: ApiError; meta: { requestId: string } }
export type ApiEnvelope<T> = SuccessEnvelope<T> | FailureEnvelope;
export type SseEvent = ContentDeltaEvent | ReasoningDeltaEvent | ToolCallEvent | ReferenceSourceEvent | TaskStatusEvent | ReportEvent | CompleteEvent | ErrorEvent;
```

- [ ] **Step 4: 验证 GREEN**

Run: `npm run contracts:typecheck`，然后 `npm run contracts:test`。

Expected: 全部 exit 0。

### Task 2: 对齐 FastAPI/Pydantic

**Files:**
- Create: `apps/backend/src/super_ai/api_contracts.py`
- Create: `apps/backend/src/super_ai/api_responses.py`
- Create: `apps/backend/src/super_ai/request_id.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Modify: `apps/backend/tests/test_app.py`
- Create: `apps/backend/tests/test_api_contracts.py`
- Create: `apps/backend/tests/test_contract_manifest.py`

**Interfaces:**
- Produces: `SuccessEnvelope[T]`、`FailureEnvelope`、`ApiErrorModel`、`AppError`、`success_response()`、`error_response()`、`request_id_middleware()` 与八种 SSE Pydantic 模型。
- Consumes: contracts manifest 的错误、path、事件和 lifecycle 目录。

- [ ] **Step 1: 写失败测试**

在测试 app 上增加仅测试使用的 known-error、validation 和 crash 路由；分别断言 HTTP status、四类 envelope、字段路径、内部异常文本不泄露、request ID header/meta 一致，以及 `/health` OpenAPI operationId 为 `getHealth`。

- [ ] **Step 2: 验证 RED**

Run: `cd apps/backend && uv run pytest tests/test_app.py tests/test_api_contracts.py tests/test_contract_manifest.py -q`

Expected: 因新模型/helper/handler 缺失或旧 health 裸响应而失败。

- [ ] **Step 3: 实现最小后端边界**

`X-Request-ID` 只接受 `[A-Za-z0-9._:-]{1,128}`；否则生成 UUID。validation details 使用：

```json
{"fields":[{"path":"query.limit","type":"int_parsing","message":"Input should be a valid integer"}]}
```

未处理异常固定使用 `SYSTEM_INTERNAL_ERROR`，不传原始异常 message。Pydantic 输出统一使用 `model_dump(mode="json", by_alias=True, exclude_none=True)`。

- [ ] **Step 4: 验证 GREEN**

Run: `cd apps/backend && uv run pytest && uv run ruff check . && uv run pyright`

Expected: 全部 exit 0。

### Task 3: 建立前端 typed transport

**Files:**
- Create: `apps/frontend/src/transport/apiClient.ts`
- Create: `apps/frontend/src/transport/apiClient.test.ts`
- Create: `apps/frontend/src/transport/sseClient.ts`
- Create: `apps/frontend/src/transport/sseClient.test.ts`

**Interfaces:**
- Produces: `createApiClient(options).request<T>() -> Promise<{data:T;requestId:string}>`、`ApiClientError`、`SseFrameParser.push()`、`createSseClient(options).stream()`。
- Consumes: `ApiEnvelope<T>`、`ApiError`、`SseEvent`，全部来自 contracts entrypoint。

- [ ] **Step 1: 写 apiClient 失败测试**

使用可控 fetch fake 返回真实 Response；断言成功解包、失败抛 typed error、Authorization 和 X-Request-ID 只在 provider 返回非空值时注入。

- [ ] **Step 2: 写 SSE 失败测试**

以手写 frame fixture 验证半帧不产出、后续 chunk 补齐后产出、单 chunk 两帧、CRLF、多 data 行、tool.call 和 error 事件。

- [ ] **Step 3: 验证 RED**

Run: `npm run frontend:test`

Expected: 因 transport 模块不存在而失败。

- [ ] **Step 4: 实现并验证 GREEN**

parser 规范化 CRLF，以空行切 frame，忽略 `:` 注释，连接多个 `data:` 行后 `JSON.parse` 为 `SseEvent`。使用 `TextDecoder.decode(chunk, {stream:true})`，结束时 flush decoder 和 parser。

Run: `npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build`。

Expected: 全部 exit 0。

### Task 4: 跨语言治理与说明

**Files:**
- Create: `tests/test_api_contract_governance.py`
- Modify: `packages/api-contracts/README.md`
- Modify: `apps/backend/README.md`
- Modify: `apps/frontend/README.md`

**Interfaces:**
- Produces: manifest 与 Python 常量/序列化样例一致性、允许定义合同的文件白名单、后续“合同先行”扩展说明。

- [ ] **Step 1: 写治理失败测试并验证 RED**

测试读取 manifest，调用真实 Pydantic 序列化，并扫描 `apps/frontend/src` 与 `apps/backend/src`；只有 contracts entrypoint 和后端镜像模块可声明八种 type 的完整目录，transport 必须以 import 消费。

Run: `cd apps/backend && uv run pytest ../../tests/test_api_contract_governance.py -q`

Expected: 在镜像/说明尚未完全对齐时失败。

- [ ] **Step 2: 完成最小治理实现并验证 GREEN**

Run: `cd apps/backend && uv run pytest ../../tests/test_api_contract_governance.py -q`

Expected: exit 0。

- [ ] **Step 3: 更新 README**

只记录已实现的合同模块、后续先改合同再加 endpoint/event 的顺序，以及现有验证命令；不声称产品功能已实现。

### Task 5: 完整门禁、语义验证、同步与归档

**Files:**
- Modify: `openspec/changes/define-api-and-sse-contracts/tasks.md`
- Sync: `openspec/specs/api-and-sse-contracts/spec.md`
- Modify by sync: `openspec/specs/monorepo-foundation/spec.md`

- [ ] **Step 1: 运行完整工程门禁**

Run contracts typecheck/test；backend Ruff/Pyright/pytest；frontend typecheck/test/build/secret；docs build；`openspec validate --all`；`git diff --check`。

- [ ] **Step 2: 执行 `$openspec-verify-change define-api-and-sse-contracts`**

逐 requirement/scenario 映射实现与测试；CRITICAL 必须修复，WARNING 必须处理或记录明确理由，然后重跑受影响及完整门禁。

- [ ] **Step 3: 同步并归档**

使用 archive workflow 内联执行 spec sync；逐份比较 delta 与主规格，确认无剩余差异后移动到日期归档目录。

- [ ] **Step 4: 归档后验证**

Run: `openspec validate --all`、`openspec list --json`、`git diff --check`。

Expected: 主规格有效、无 active change、补丁格式通过。
