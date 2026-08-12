## Purpose

本能力提供 tenant-safe 的持久后台任务与事件运行边界，使长耗时工作不依赖客户端连接或单次进程存活，并能在失败、超时和进程重启后确定地恢复或终止。

## ADDED Requirements

### Requirement: 任务与事件由迁移后的 SQLite 持久保存
系统 SHALL 以 Alembic 管理的 `background_jobs` 与 `background_job_events` 保存任务和事件。任务 MUST 包含 owner、kind、resourceType/resourceId、status、payload、attempt/maxAttempts、timeoutSeconds、availableAt、leaseOwner/leaseExpiresAt、cancelRequestedAt、retryOfJobId、errorMessage 以及 created/updated/started/completed 时间戳；MUST NOT 虚构 `heartbeatAt` 或 `result` 列。

#### Scenario: 新数据库升级到最新版本
- **WHEN** 对空 SQLite 数据库执行 `alembic upgrade head`
- **THEN** 两张后台任务表、约束与索引均存在，且 metadata 与迁移结构一致

#### Scenario: 心跳续租
- **WHEN** 正在运行的 worker 发送 heartbeat
- **THEN** 系统只延长 `leaseExpiresAt` 并记录必要事件，不写入不存在的 heartbeat 列

### Requirement: Repository 强制 owner scope
所有面向用户的任务 list、get、cancel、retry 与 event 查询 MUST 显式接收 `owner_user_id`，并在同一 SQL 语句中约束 owner 与任务标识。另一个用户的任务与不存在任务 MUST 返回相同的不可枚举资源不存在语义。

#### Scenario: 跨 owner 读取或修改任务
- **WHEN** 用户 B 使用用户 A 的任务 ID 查询、取消、重试或读取事件
- **THEN** 操作不返回或修改 A 的数据，并使用与不存在任务相同的安全错误

#### Scenario: owner 查询自己的任务
- **WHEN** 已认证用户按 owner scope 列表或读取任务和增量事件
- **THEN** 只返回属于该用户的记录

### Requirement: Worker 使用租约可靠领取与恢复任务
系统 SHALL 通过原子数据库操作唯一领取可用任务，默认运行两个 worker、租约 30 秒且轮询间隔约 0.2 秒。worker MUST 续写租约；过期租约 MUST 可由其他 worker 或重启后的进程恢复；worker 崩溃 MUST NOT 造成永久悬挂。

#### Scenario: 并发领取同一任务
- **WHEN** 多个 worker 同时尝试领取同一个可用任务
- **THEN** 只有一个 worker 获得有效租约并执行 handler

#### Scenario: 进程重启恢复过期任务
- **WHEN** running 任务的 worker 消失且租约过期后 runtime 重启
- **THEN** 新 worker 在最大尝试次数内重新领取并继续处理任务

### Requirement: Handler 注册与执行受控
handler SHALL 按任务 kind 显式注册。任务执行 MUST 支持最大尝试次数、最大 30 秒的指数退避、单任务 timeout 与协作式取消；runtime 使用实际 UTC 时间和异步休眠，不公开虚构的 clock 构造参数。

#### Scenario: handler 暂时失败
- **WHEN** handler 在尚有剩余尝试次数时失败
- **THEN** 任务回到 queued、增加 attempt，并将 availableAt 设置为不超过 30 秒的指数退避时间

#### Scenario: handler 耗尽尝试或超时
- **WHEN** 任务达到最大尝试次数，或一次执行超过 timeoutSeconds 且无法继续重试
- **THEN** 任务进入 failed，保存脱敏错误并释放租约

#### Scenario: 取消排队或运行任务
- **WHEN** owner 请求取消 queued 或 running 任务
- **THEN** queued 任务直接进入 cancelled，running 任务设置 cancelRequestedAt 并由 handler/runtime 协作终止

### Requirement: 持久事件支持断连后重放
任务事件 sequence MUST 单调递增，Repository MUST 支持 `list_events(after_sequence=...)`。事件至少表达 queued、running、succeeded、failed、cancelled 等状态变化。客户端或 SSE 断开 MUST NOT 取消任务；消费者 MUST 可从 sequence=0 或最后已处理 sequence 之后重放持久事件。

#### Scenario: 增量读取事件
- **WHEN** 消费者传入某个 `after_sequence`
- **THEN** 系统只按升序返回 sequence 更大的 owner-scoped 事件

#### Scenario: 客户端断开后恢复
- **WHEN** 客户端断开期间任务继续产生事件并在之后重连
- **THEN** 任务不被取消，消费者可从持久事件恢复状态

### Requirement: 受保护 API 管理 owner 的后台任务
系统 SHALL 提供 `GET /background-jobs`、`GET /background-jobs/{id}`、`POST /background-jobs/{id}:cancel` 与 `POST /background-jobs/{id}:retry`。全部 path MUST 使用 bearer 认证、统一 envelope/request ID，并复用共享 401、403 与资源不存在错误。

#### Scenario: 已认证用户管理任务
- **WHEN** 用户通过四个 path 列表、读取、取消或重试自己的任务
- **THEN** 响应使用共享 BackgroundJob DTO 和统一成功 envelope

#### Scenario: 未认证访问
- **WHEN** 请求未携带有效 bearer token
- **THEN** API 返回共享 `AUTH_REQUIRED` 失败 envelope

### Requirement: 日志与错误不泄露敏感 payload
worker 与 Repository 的日志、事件和对外错误 MUST 对 password、secret、token、apiKey、authorization 等敏感字段脱敏；未处理异常 MUST NOT 把原始 payload 或凭据返回客户端。

#### Scenario: handler 对含凭据 payload 抛错
- **WHEN** handler 异常文本或任务 payload 包含敏感值
- **THEN** 持久 errorMessage、事件和日志不包含该敏感值
