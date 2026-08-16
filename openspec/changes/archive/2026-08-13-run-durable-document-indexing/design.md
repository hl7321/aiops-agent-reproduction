## Context

参见 [proposal.md](./proposal.md)。P06 已提供按最多 10 条分批且保序的 Qwen embedding provider；P07 提供 lazy、tenant-safe Milvus adapter；P09 提供 SQLite lease worker、handler registry、重试/取消/恢复；P10 保存可索引正文和 chunking config，并提供统一 splitter。当前缺口是把四个边界组装为一个 durable、owner-scoped 的索引领域，而不在上传路由或模块 import 时创建外部 client。

## Goals / Non-Goals

**Goals:**

- 领域任务与 background job 分层持久化，能由 resourceType/resourceId 恢复关联。
- handler 对单个文档执行确定、有测试证据的替换式向量索引流程。
- 五种状态在 SQLite record、Pydantic、TypeScript 和 API 中一致。
- 所有外部 client 通过显式 factory/依赖注入创建；import、上传和空闲 worker 不联网。

**Non-Goals:**

- 不实现检索、RAG、知识库页面、进度 SSE 或 HTTP Last-Event-ID。
- 不新增多个知识库、对象存储或应用 Compose 服务。
- 不实现 SQLite/Milvus 两阶段提交，也不承诺跨系统原子替换。
- 不用 `asyncio.create_task` 绕开 P09 runtime，不生成 fallback embedding。

## Decisions

### 1. 领域 task 与通用 job 使用 resource 关联，不保存 jobId

`document_index_tasks` 只保存领域可见事实：owner、KB、document、状态、failureReason、retryOfTaskId 与时间戳。创建任务时在同一 SQLite transaction 中写入领域 task 和 `background_jobs`，其中 `kind=document.index`、`resource_type=document_index_task`、`resource_id=task.id`，payload 只保存 task/owner/KB/document 的非敏感定位信息。

不选择 task.job_id：它会把通用 runtime 主键泄漏为领域 schema，并与用户明确的无 jobId 边界冲突。反向查询依靠 background_jobs 的 resource 索引/Repository 方法。

### 2. 领域状态由 handler 显式推进，runtime 终态作为兜底协调

创建即 pending；handler 开始后在 owner scope 内置 running，成功后同时把 task/document 置 succeeded。handler 捕获异常仅用于把 task/document 写 failed 和保存 `redact_error` 后重新抛出，使 P09 runtime 继续记录 job 失败/退避；绝不静默吞错。协作式取消由 handler 在阶段边界调用 cancellation check，runtime 完成 cancelled 后通过 outcome hook/协调器把领域任务置 cancelled。

备选方案是只从 background job 实时推导状态，但这不能保存领域 failureReason、retry 来源，也不能高效 owner-scoped 查询文档状态。

### 3. handler 使用短事务读取/状态写入，外部 I/O 不持有 SQLite transaction

handler 先用独立 session 按 owner+KB+document+task 读取不可变快照并标 running，关闭 transaction 后执行 splitter/embedding/Milvus。成功或失败再开短事务写终态。这接受数据库与向量库短暂不一致，并让 retry 通过“先删除本 scope 旧向量、再一次插入新集合”收敛。

不选择跨系统锁或补偿事务：Milvus 与 SQLite 没有共享事务协调器，宣称原子会制造错误可靠性预期。

### 4. 验证全部 embedding 后才触碰 Milvus

handler 复用 P06 provider 的 `embed_documents` 保序分批合同；额外验证向量数等于 chunk 数且每条恰为 1024 维。只有验证通过才显式 `initialize()`，然后 `delete_document(scope,kb,document)`，最后一次 `insert_chunks(scope, records)`。chunkId 使用基于 documentId、chunk ordinal 和内容摘要的确定性值，使同一文档重试可复现。

不逐 chunk insert：部分写入会扩大失败恢复面；P07 adapter 已支持批量 records。

### 5. 上传和调度由前端 transport 显式串联

上传 endpoint 不改为隐式 enqueue。共享 contracts 暴露三个 index task 操作；P08 的 typed transport 增加 `knowledgeClient.uploadDocument()` 与 `createIndexTask()`，调用方的首次上传流程在第一个成功后显式调用第二个。当前不实现知识 UI，但用客户端测试证明请求顺序和上传失败不调度。

### 6. runtime 组装保持 lazy 且可测试

生产 app lifespan 在显式加载本地 JSON 后创建 Qwen provider 与 Milvus adapter factory，并把 `document.index` handler 注册进既有 registry；测试注入 fake handler dependencies。模块 import、app factory 本身及上传路由不解析真实凭据、不 connect Milvus。若当前应用启动允许空凭据，handler factory 延迟到实际任务执行才安全失败。

## Risks / Trade-offs

- **[Milvus delete 成功而 insert 失败导致暂时无向量]** → task/document 为 failed，retry 重跑完整替换流程；API 不显示 succeeded。
- **[worker 在 Milvus insert 后、SQLite 成功写前崩溃]** → lease 恢复后用稳定 chunkId 先 scoped delete 再 insert，最终收敛。
- **[多个重建任务并发覆盖同一文档]** → Repository 创建时拒绝同一文档存在 pending/running 任务并返回 conflict；历史 succeeded/failed/cancelled 不阻止新任务。
- **[错误文本泄露凭据]** → 复用 P09 `redact_error`，领域 failureReason 与 background job error 均只保存脱敏文本。
- **[取消发生在不可中断的同步 Milvus 调用中]** → PyMilvus 调用在线程中完成后再检查取消；任务不标 succeeded，并由后续 retry/重建收敛。

## Migration Plan

1. 先部署 Alembic revision 创建空 `document_index_tasks` 和索引；不回填旧文档任务，既有文档保持当前状态，可由 owner 手动重建。
2. 部署 contracts/API 和 handler registry；应用启动仍不自动连接 Qwen/Milvus。
3. 客户端改为上传成功后显式创建首次任务。
4. 回滚时先停止 worker；downgrade 只删除领域 task 表。Milvus 中已成功向量仍由文档 scope 管理，回滚前按业务需要备份 SQLite。
