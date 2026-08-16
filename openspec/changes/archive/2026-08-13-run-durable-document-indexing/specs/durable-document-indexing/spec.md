## Purpose

本能力把文档切分、Qwen embedding 与 Milvus 向量替换纳入 owner-scoped durable job，使索引在客户端断开、worker 重启和外部服务失败后仍可追踪、重试和安全恢复。

## ADDED Requirements

### Requirement: 索引任务具有独立且可追溯的领域记录
系统 SHALL 以 Alembic 管理 `document_index_tasks`，保存 id、owner、knowledgeBase、document、`pending|running|succeeded|failed|cancelled` 状态、可选安全 failureReason、可选 retryOfTaskId 与 created/updated/started/completed 时间戳。表 MUST NOT 包含 jobId；底层 background job MUST 通过 `resourceType=document_index_task` 与 `resourceId=taskId` 建立关联，queued MUST 映射为领域 pending。

#### Scenario: 空数据库升级
- **WHEN** 对新 SQLite 数据库执行 `alembic upgrade head`
- **THEN** 领域任务表、外键、状态约束和 owner 查询索引存在，且不存在 jobId 列

#### Scenario: queued job 对外显示 pending
- **WHEN** 索引任务已持久入队但尚未被 worker 领取
- **THEN** 领域 DTO 返回 pending，且可通过 resourceType/resourceId 找到底层 job

### Requirement: 首次索引与重建必须由客户端显式创建
文档上传 API MUST 只创建文档，不自动启动进程内任务或 durable job。客户端在上传成功后 SHALL 显式创建首次 index task；owner 也 SHALL 能对已有活动文档手动创建新任务以重建索引。创建成功 MUST 同一事务保存领域任务并入队 background job，客户端断开 MUST NOT 取消任务。

#### Scenario: 上传后尚未创建索引任务
- **WHEN** 客户端只完成文档上传而未调用 index-task API
- **THEN** 文档存在但没有领域索引任务或对应 background job

#### Scenario: 客户端显式创建首次任务
- **WHEN** 上传成功后客户端调用 index-task 创建 API
- **THEN** 系统返回 pending 领域任务并持久入队，background job 使用任务 id 作为 resourceId

#### Scenario: owner 手动重建
- **WHEN** owner 对已完成或失败的活动文档再次创建 index task
- **THEN** 系统创建新的 pending 任务而不修改历史任务，并在执行时替换该文档旧向量

### Requirement: Durable handler 严格按可恢复顺序执行
handler MUST 重新按 owner+KB+document scope 读取活动文档，使用文档保存配置调用统一 splitter 产生全部 chunks，按输入顺序取得 1024 维真实 embedding，显式 initialize Milvus，再使用完整 tenant+KB+document scope 删除旧 chunks，并以一次批量 insert 写入全部新 chunks，最后更新任务和文档状态。系统 MUST NOT 宣称 SQLite 与 Milvus 跨系统原子；任何步骤失败 MUST 保留可重试的 failed 状态且不得把文档标为 succeeded。

#### Scenario: 成功执行索引任务
- **WHEN** worker 领取 pending 索引任务且所有依赖成功
- **THEN** 调用顺序为读取、切分、embedding、initialize、删除、单次插入、状态成功，任务与文档均为 succeeded

#### Scenario: 外部步骤失败
- **WHEN** splitter、embedding、Milvus initialize/delete/insert 任一步骤抛错
- **THEN** 错误不被吞掉，任务和文档最终为 failed，failureReason 已脱敏且不存在虚构或部分成功状态

### Requirement: Embedding 分批且 Milvus 单次批量插入
当 chunk 数大于 10 时，embedding provider MUST 以每批最多 10 条原始字符串调用并保持结果与 chunks 完全同序，不得丢失、重排或生成假向量。Milvus MUST 仍只执行一次 insert，且该次包含全部 chunk records；向量数量或维数不匹配 MUST 在删除旧向量前失败。

#### Scenario: 十条以上 chunks
- **WHEN** splitter 按顺序产生 23 个 chunks
- **THEN** embedding 调用批量为 10、10、3，Milvus insert 只调用一次并按原顺序收到 23 条记录

#### Scenario: embedding 返回形状错误
- **WHEN** provider 返回数量不等或任一向量不是 1024 维
- **THEN** handler 失败且未初始化、删除或插入 Milvus

### Requirement: 每条向量携带完整可信追溯字段
每个写入记录 MUST 包含稳定 chunkId、documentId、knowledgeBaseId、ownerUserId、tenantId、content、source、createdAt、vector 与 chunking metadata。tenantId MUST 等于当前 owner user id；metadata MUST 至少保留 chunk 顺序、strategy、文档/KB/owner/tenant 追溯字段，且不得被不可信 metadata 覆盖。

#### Scenario: 检查写入记录
- **WHEN** handler 为文档生成并插入多个 chunks
- **THEN** 每条记录字段完整，chunkId 可由任务重试稳定复现，owner/tenant/KB/document 与当前 scope 一致

### Requirement: 重试、取消和重启恢复保持领域状态一致
retry API MUST 为失败或取消任务创建新的领域 attempt，并设置 retryOfTaskId 指向来源，同时入队新的 background job；不得复用旧任务或伪造 jobId。协作式取消、timeout、失败、成功与过期 lease 重启恢复 MUST 同步为五种领域状态；worker 重启后 SHALL 通过持久 payload/resource 继续执行，客户端连接状态不参与生命周期。

#### Scenario: 重试失败任务
- **WHEN** owner 对 failed 任务调用 retry
- **THEN** 返回新的 pending 任务，其 retryOfTaskId 指向来源，来源任务保持 failed

#### Scenario: 取消排队或运行任务
- **WHEN** owner 通过底层 durable job 边界取消索引任务
- **THEN** 领域任务和文档不会进入 succeeded；任务最终映射为 cancelled

#### Scenario: worker 重启恢复
- **WHEN** worker 在 running 任务中断后租约过期并重新启动
- **THEN** 同一领域任务由持久 background job 恢复执行，不创建临时 asyncio task 或新领域记录

### Requirement: 索引任务始终强制 owner 与父资源 scope
创建、详情、retry、handler 文档读取和状态更新 MUST 显式接收 owner_user_id，并在同一 SQL 中约束 owner+KB+document+task。其他用户的 task/document MUST 使用不可枚举语义且不得初始化 Milvus、删除或写入向量。

#### Scenario: 跨 owner 查询或重试
- **WHEN** 用户 B 使用用户 A 的 KB、document 或 task id 请求详情、重试或执行
- **THEN** 不返回或修改 A 的记录，且没有任何外部 provider/Milvus 调用

### Requirement: 自动化与真实 smoke 边界诚实
自动化测试 MUST 使用临时 SQLite、fake embedding 与 fake Milvus client，且 import 不创建外部 client或连接网络。真实 Qwen+Milvus smoke SHALL 仅在 ignored 本机 JSON 同时含有效凭据、Milvus 服务可用且显式执行时运行；未满足条件时 MUST 明确记录未执行。

#### Scenario: 自动化门禁无真实凭据
- **WHEN** 本机 Qwen key 为空或 Milvus 不可用
- **THEN** fake 自动化仍可验证全部协议，但报告明确写“真实 Qwen+Milvus smoke 未执行”
