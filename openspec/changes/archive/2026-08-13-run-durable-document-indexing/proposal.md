## Why

P10 已能安全保存和切分文档，但索引仍没有可恢复的执行路径。文档切分、Qwen embedding 与 Milvus 写入耗时且跨越两个持久系统，必须由 P09 durable job 承载，才能在客户端断开、进程重启和外部服务失败后确定恢复，而不是退回临时 `asyncio` 任务。

## What Changes

- 新增 owner-scoped `document_index_tasks` 领域记录和 Alembic migration；通过 background job 的 `resourceType=document_index_task`、`resourceId=taskId` 关联，不增加 `jobId` 列。
- 文档上传继续只创建文档；客户端在上传成功后显式创建首次 index task。提供任务创建、详情和 retry/rebuild API。
- 注册 durable document indexing handler，严格执行：重新读取 owner-scoped 文档、复用 P10 splitter、Qwen embedding、显式初始化 Milvus、清理旧向量、一次批量插入全部 chunks、更新领域任务和文档状态。
- 统一 `pending/running/succeeded/failed/cancelled` 的领域状态、UI-ready DTO、错误脱敏、来源任务追溯和 queued→pending 映射。
- 增加迁移、合同、handler 顺序、批处理、metadata、重试/取消/重启、跨 owner 与 API envelope 自动化测试；真实 Qwen/Milvus smoke 仅在本机配置和服务可用时执行并如实记录。
- 不实现完整检索或知识库 UI，不伪造 embedding，不宣称 SQLite 与 Milvus 跨系统原子事务。

## Capabilities

### New Capabilities

- `durable-document-indexing`：定义可恢复的文档索引任务、执行顺序、状态机、失败恢复、向量写入和 tenant 安全边界。

### Modified Capabilities

- `knowledge-documents-and-chunking`：明确上传与索引任务分离，并把文档索引状态收敛为五种领域状态。
- `api-and-sse-contracts`：增加 DocumentIndexTask DTO、创建/详情/retry 操作及状态目录。

## Impact

- 后端新增 migration、索引领域 Repository/handler/service/router 与 runtime 组装，复用 P06 embedding、P07 Milvus adapter、P09 worker 和 P10 splitter/document Repository。
- `packages/api-contracts` 增加索引任务类型与机器可读 OpenAPI 目录；知识文档 DTO 的 index status 变为稳定判别联合。
- 自动化测试继续使用临时 SQLite、fake embedding 和 fake Milvus client；模块导入、上传请求和客户端断开均不得创建临时后台任务或连接外部服务。
