## Context

参见 [proposal.md](./proposal.md)。现有项目已经具备 SQLAlchemy 2 async、Alembic、认证身份、OwnerScope 和统一 contracts，但尚无可跨请求、断连或重启保存执行状态的后台运行时。SQLite 是当前本地持久化实现，领域服务不得接收 ORM model，import 期间不得打开数据库。

## Goals / Non-Goals

**Goals:**

- 以 SQLite 记录为任务和事件的唯一事实来源，提供可替换的 Repository Protocol 与不可变 record。
- 在 FastAPI lifespan 内托管有限并发 worker，并让退出流程可等待、可取消且释放数据库 runtime。
- 用原子 claim 与有限租约保证并发唯一领取和崩溃后恢复。
- 让 API、Pydantic 与 TypeScript contracts 对任务及错误保持一致，并强制 owner scope。

**Non-Goals:**

- 不实现文档索引或 AIOps 业务 handler，不增加公开 enqueue endpoint。
- 不引入 Celery、Redis、消息队列或新 Compose 服务。
- 不实现 HTTP Last-Event-ID 或结果存储列；事件查询仅提供持久重放基础。
- 不提供可注入 clock；当前 runtime 直接使用 `_utc_now()` 与 `asyncio.sleep()`。

## Decisions

### 1. 规范化双表与不可变领域 record

Alembic 新增任务主表和事件表。任务高频筛选、租约、owner 与资源字段使用独立列；payload 与 event data 使用统一 JSON 序列化。事件使用数据库自增整数 sequence 形成全局单调游标，查询同时约束 owner 和 job。

选择全局 sequence 而不是每任务 `max(sequence)+1`，因为 SQLite 自增可以避免并发计算冲突，消费者只依赖单调性而非连续性。ORM 仅留在 `super_ai.memory.extended_sqlite`，领域层只接收冻结 record。

### 2. 原子 UPDATE…RETURNING claim 与租约

claim 在单个写事务中选取 available 的 queued 任务或 lease 已过期的 running 任务，并以带候选条件的 UPDATE…RETURNING 设置 worker、租约、running 状态和 attempt。heartbeat 使用 `job_id + lease_owner + running` 条件延长 lease；完成也必须持有同一租约。

相比“先 SELECT 再 UPDATE”，该方式不会让两个并发 worker 同时执行同一领取结果。相比永久 running 标记，有限租约允许崩溃和重启后的 worker 接管。达到最大尝试次数的过期任务由回收路径终止为 failed。

### 3. 持久任务与进程内执行器分离

入队先提交 SQLite；worker pool 只执行数据库已领取的任务。lifespan 使用受管理的异步任务组启动默认两个循环，退出先发停止信号，再取消/等待执行器，最后释放数据库 engine。这里允许受管理协程承载执行，但禁止 endpoint 以一次性 `asyncio.create_task` 作为任务事实来源。

handler registry 按 kind 显式注册，未注册 kind 作为可重试执行失败处理。handler 获得上下文，可在阶段边界检查持久 `cancelRequestedAt`；runtime 也在 heartbeat 周期检测取消。

### 4. 重试、超时与取消采用明确状态机

状态为 queued、running、succeeded、failed、cancelled。claim 时 attempt 增加；失败且 `attempt < maxAttempts` 时回到 queued，退避为 `min(30, 2 ** (attempt - 1))` 秒。单次 handler 使用任务 timeoutSeconds 限时。queued 取消立即终止；running 取消设置时间戳，由 heartbeat/handler 协作结束。

不增加 heartbeatAt 或 result：心跳唯一含义是 leaseExpiresAt 延长，业务输出由事件或后续领域表承载。

### 5. Owner scope 分离用户 API 与内部租约操作

用户可见 Repository Protocol 的 list/get/cancel/retry/list_events 均把 `owner_user_id` 作为首个业务参数。内部 claim/heartbeat/finish 通过不可伪造的 lease owner 约束，不接受 HTTP 用户输入。跨 owner 与不存在任务返回同一个 `BUSINESS_RESOURCE_NOT_FOUND`。

### 6. 共享 contracts 先于路由

`packages/api-contracts` 提供任务 DTO、状态和机器可读 path；Python 建立同形 Pydantic 镜像。API 复用 bearer dependency、统一 envelope 和 request ID。当前 API 只管理既有任务；后续领域服务通过注入的 enqueue 边界创建任务。

### 7. 安全错误与 payload 处理

JSON 序列化使用稳定、可测试的编码器。持久 errorMessage 先按敏感键和值脱敏并限制长度；日志仅记录 job id/kind/status 等结构化元数据，不输出完整 payload。内部异常通过共享安全错误目录映射。

## Risks / Trade-offs

- [SQLite 写锁限制高并发吞吐] → 当前默认并发仅 2，claim 与状态更新保持短事务；Repository Protocol 为未来 PostgreSQL 保留替换边界。
- [租约过短造成仍在执行的任务被接管] → heartbeat 周期显著小于 30 秒租约，并要求 finish 校验 lease owner；后续可通过本地 JSON typed 配置扩展，但本 change 固定安全默认值。
- [Python 协作取消无法强杀不可取消的同步调用] → handler 必须使用异步可取消边界并检查上下文；timeout 后释放/重试由状态机处理。
- [全局事件 sequence 存在间隙] → 合同只保证单调而不保证连续，重放使用 `>` 游标。
- [进程在提交外部副作用后、提交成功状态前崩溃会重复执行] → handler 必须按资源键实现幂等；本 change 不承诺 exactly-once 外部副作用。

## Migration Plan

1. 扩展共享 contracts 和验收测试。
2. 执行 Alembic migration 创建空任务/事件表，不迁移既有业务数据。
3. 部署应用后由 lifespan 启动 worker；没有已登记 handler 的任务会按有限重试规则失败，不静默丢失。
4. 回滚应用前先停止 worker；Alembic downgrade 可删除本 change 的空表或明确丢弃后台任务历史，生产数据回滚前必须备份。
