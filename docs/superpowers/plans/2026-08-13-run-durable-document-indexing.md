# Durable Document Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 P09 持久任务执行 P10 文档切分、P06 Qwen embedding 与 P07 Milvus 替换式写入，并提供 owner-scoped 状态与重试 API。

**Architecture:** `document_index_tasks` 保存 UI-ready 领域状态，`background_jobs` 通过 resource type/id 关联；service 在同一 SQLite transaction 创建两种记录。handler 使用短事务读取/推进状态，外部 I/O 顺序为 splitter、embedding、Milvus initialize/delete/单次 insert，失败脱敏后重抛给 durable runtime。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、Qwen OpenAI-compatible embedding、PyMilvus adapter、pytest、TypeScript 5.6、Vitest。

## Global Constraints

- 不增加 `jobId` 领域列或 DTO 字段；background job 只用 `resourceType=document_index_task`、`resourceId=taskId` 关联。
- 公开状态只有 pending/running/succeeded/failed/cancelled，queued 映射 pending。
- embedding 每批最多 10 且保序；Milvus 对全部 chunks 只执行一次 insert。
- 上传只保存文档，客户端显式 POST 创建首次任务；禁止临时 `asyncio.create_task` 业务调度。
- 所有用户操作首个业务参数为 `owner_user_id`；外部 client 仅在 handler 显式执行路径创建。

---

### Task 1: 合同与 Alembic/Repository

**Files:** `packages/api-contracts/src/document-indexing.ts`、manifest、`api_contracts.py`、migration、ORM/Repository 和测试。

**Interfaces:** `DocumentIndexTaskRecord`；`SqliteDocumentIndexTaskRepository.create/get/transition/retry`；background store `enqueue` 与 resource lookup。

- [x] 写合同和 migration/Repository 测试，运行并确认因类型、表和 API 缺失而失败。
- [x] 实现 migration、records、Repository、五种合同状态和三种 OpenAPI operation。
- [x] 运行定向测试至通过并更新 OpenSpec 1.x tasks。

### Task 2: Handler 与 durable runtime 协调

**Files:** `super_ai/document_indexing/handler.py`、service/dependencies、background runtime/store、测试。

**Interfaces:** `DocumentIndexHandlerDependencies`；`create_document_index_handler(...)`；handler kind `document.index`。

- [x] 写 23 chunks、顺序/metadata、向量错误、失败/取消/恢复测试并观察 RED。
- [x] 实现 owner-scoped 快照、状态推进、稳定 chunkId、embedding validation 与单次 Milvus insert。
- [x] 通过 resource 状态协调注册 handler，验证取消/失败/重启终态。

### Task 3: API 与前端显式调度

**Files:** indexing router/service、knowledge DTO、frontend `knowledgeClient.ts` 及测试。

**Interfaces:** POST index-tasks、GET task、POST task:retry；`uploadAndCreateIndexTask` 顺序方法。

- [x] 写上传零任务、创建/详情/retry/重建/跨 owner API 和前端调用顺序测试并观察 RED。
- [x] 实现 API/DI 与 typed transport，不新增知识 UI。
- [x] 验证上传失败不 enqueue、客户端断开不影响持久任务。

### Task 4: 治理、门禁与归档

**Files:** import/policy tests、smoke README、OpenSpec artifacts/specs。

**Interfaces:** fake 自动化为默认；真实 smoke 仅显式运行。

- [x] 增加 import-safety、no-jobId/no-fake-vector、Repository 参数治理与 smoke 说明。
- [x] 运行 migration、backend/contracts/frontend/OpenSpec/diff 全门禁。
- [ ] 执行 verify，修复全部 CRITICAL/WARNING，同步三份 specs 并归档。
