## Why

文档索引与 AIOps 等长耗时操作不能依赖 HTTP 连接或进程内临时任务存活。现在需要先建立 SQLite 持久化任务、租约与事件重放边界，使任务在客户端断开或进程重启后仍可安全恢复，并继承既有 owner 隔离规则。

## What Changes

- 增加 Alembic 管理的 `background_jobs` 与 `background_job_events` 规范化表，以及不可变领域 record 和 owner-scoped Repository。
- 增加按 kind 注册 handler 的持久化 worker runtime，在 FastAPI lifespan 中托管固定并发 worker，并实现原子领取、租约续期、过期恢复、超时、退避重试和协作式取消。
- 增加单调 sequence 的持久事件流和 `after_sequence` 重放能力；明确 SSE 连接断开不取消任务，暂不声明 HTTP Last-Event-ID 协议。
- 扩展共享 TypeScript/Pydantic contracts、机器可读 OpenAPI path 目录和 FastAPI 路由，提供后台任务列表、详情、取消与重试接口。
- 使用临时 SQLite 与 fake handler 建立并发、恢复、隔离、脱敏和 lifespan 清理的自动化验收。
- 不实现文档索引、AIOps 业务 handler、任务结果列或独立任务创建 HTTP API。

## Capabilities

### New Capabilities

- `durable-background-job-runtime`：覆盖持久任务模型、owner-scoped Repository、租约 worker、事件重放、受保护管理 API 与安全运行边界。

### Modified Capabilities

- `api-and-sse-contracts`：增加后台任务 DTO、错误目录和四个受保护 OpenAPI path 的共享合同要求。

## Impact

- 后端新增 background job 领域、SQLite adapter、Alembic migration、FastAPI router 与 lifespan worker 集成。
- `packages/api-contracts` 新增后台任务类型并扩展错误和 path manifest。
- 后续文档索引与 AIOps 必须通过该 runtime 入队和消费持久事件，不得以临时 `create_task` 作为最终任务运行时。
- 不新增外部基础设施或环境变量配置来源；测试继续使用临时 SQLite，不依赖开发者本机数据库。
