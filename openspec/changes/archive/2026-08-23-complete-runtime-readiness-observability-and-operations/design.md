## Context

参见 `proposal.md` 的动机。当前应用已具备 app factory、显式 SQLite lifespan、延迟 Milvus adapter、Qwen readiness、owner-scoped MCP gateway 与 request ID middleware，但只有进程级 `/health`；脱敏逻辑散落于若干领域，尚无统一依赖检查编排、本进程指标或 completion log。本 change 跨后端、共享合同、启动脚本和交付文档，必须保持 import 无副作用、项目配置只来自显式本地 JSON、应用不进入 Compose。

## Goals / Non-Goals

**Goals:**

- 用同一组可注入检查器驱动 `/ready` 与 `/config/check`，保证行为一致且单测不联网。
- 把配置有效性、依赖可达性和进程存活拆成不同信号。
- 提供最小、线程安全的进程内 HTTP 指标与结构化安全日志。
- 让两个平台启动脚本和中文文档成为最终本地交付入口。
- 在无真实 secret 的 fresh clone 上完成全部自动门禁。

**Non-Goals:**

- 不引入 Prometheus client 或把 `/metrics` 伪装成 Prometheus exposition。
- 不在探针中创建 schema、执行迁移、写向量、调用业务工具或修改外部状态。
- 不自动执行 P25 fixture，不代替用户确认真实 CLS/Alertmanager/SOP 目标。
- 不容器化后端、前端或官方 CLS MCP Server。

## Decisions

### 1. 运行时检查采用 request-scoped 编排器与显式注入

新增聚焦的 runtime diagnostics 模块，定义不可变结果与 SQLite、Milvus、Qwen、MCP 四个异步 checker。应用工厂只保存 typed settings、配置路径和 checker factory，不在 import 或 app construction 时创建外部 client。`/ready` 并行执行独立检查并完整收集结果；`/config/check` 先加载并验证所有 section，只有 configuration valid 才复用同一依赖编排器。

SQLite 使用已有 lifespan engine 执行只读 `SELECT 1`；Milvus 创建 adapter 后显式 connect 再 health，不 initialize collection；Qwen 复用最小 chat readiness；MCP 对配置回退来源执行真实 discovery，未配置时明确 unavailable。选择 checker 抽象而不是在 router 内硬编码，原因是自动测试需要替换真正的网络边界，同时必须验证聚合与 HTTP 行为本身。

### 2. 503 使用统一失败 envelope 并把逐项结果放入安全 details

成功响应使用 typed success DTO。部分或全部失败时使用共享 `SYSTEM_UNAVAILABLE` failure envelope，`details` 携带与成功 DTO 同构的安全诊断数据；这样遵守现有 envelope，同时不会因失败丢失成功依赖信息。`/config/check` 以 `configuration_invalid` 和 `dependencies_unavailable` 区分阶段。

备选方案是 200 加 overall failed，但会使负载均衡器和启动编排无法正确判断 readiness，因此不采用。

### 3. 指标与日志共用一个 completion middleware

在 request ID 建立之后记录 monotonic 开始时间，在 response 或异常完成时更新应用内 `ProcessMetricsRegistry`，并通过标准 logging 输出单行 JSON。registry 只累计 request count、failure count 和 duration，不按用户、query 或动态路径标签分桶，避免敏感信息和无界基数。`/metrics` 的当前请求在响应完成后才计入，因此 payload 是请求进入时的快照；测试按此确定语义。

日志序列化前使用通用递归 `redact_sensitive`，对 key 名包含 password/token/key/secret/authorization 的值替换为 `[redacted]`。completion log 由固定 allowlist 直接构造，不读取 headers/body。领域 lifecycle 通过安全 helper 接收显式 allowlist 字段；既有持久 tool audit 继续保存其规格允许的 owner-scoped arguments，但结构化运行日志只记录参数键。

### 4. 共享合同新增独立 runtime 模块

`packages/api-contracts` 新增 runtime DTO 并从 typed entrypoint 导出，manifest 先登记四个 path。后端 Pydantic 镜像与 OpenAPI operationId 通过合同测试对齐。`/health` 保持原 FoundationStatus 与绝对无外部 I/O 语义，避免 readiness 改造污染 liveness。

### 5. 启动脚本编排进程而不隐藏副作用

Unix 脚本使用 Bash，只面向 macOS/Linux/Git Bash；Windows 批处理使用 cmd 原生命令，不调用 Bash。两者验证 Git、Docker、Node/npm、uv、npx/官方 CLS MCP 命令，必要时执行明确的安装提示或项目依赖安装，复制缺失的模板配置，启动 Compose、同步后端、升级 Alembic，再把主机进程日志写入 `apps/backend/var`。

脚本从 JSON 读取 CLS 凭据仅用于构造官方 CLS MCP 子进程环境；Python 应用仍通过显式 `project.json`/`user.project.json` 路径启动。fixture 脚本不会被启动入口调用。进程 PID 写入 var，便于人工停止；当前不增加跨平台守护进程管理器。

### 6. 真实验收采用“可执行门禁 + 明确未执行清单”

自动门禁使用 tmp_path、fake transport/client 和空模板，证明内部逻辑与安全边界，不代表外部连通。真实桌面链路只有在服务、凭据和目标齐备且用户明确授权外部副作用时执行；缺项按 Qwen、Milvus、CLS MCP、CLS、Alertmanager 和浏览器链路分别记录。Windows bat 只允许在 cmd/PowerShell 实机确认，macOS 上不使用 Bash 冒充。

## Risks / Trade-offs

- [readiness 调用真实外部服务可能较慢] → 四项并行、各自沿用有界 timeout/retry，并记录 latency。
- [公开诊断 endpoint 可能暴露内部拓扑] → 只返回固定依赖名、状态、latency 与脱敏错误，不返回 URL、版本细节、配置值或凭据。
- [进程内指标重启后归零且多 worker 不聚合] → DTO 明确 scope 为 process，不宣称持久化或 Prometheus 兼容；未来可单独提案接入指标系统。
- [启动脚本跨平台进程管理差异] → 保持两个原生入口、记录 PID/日志，并把 Windows 实机验证与 Bash 语法门禁分开。
- [递归脱敏无法弥补调用方先拼接正文] → completion/lifecycle log 使用字段 allowlist，脱敏作为第二道防线而不是唯一防线。

## Migration Plan

1. 先扩展共享 DTO/manifest 与后端 RED 合同测试。
2. 实现 runtime diagnostics、指标、中间件和 app factory 注入，保持 `/health` 原行为。
3. 增加安全 lifecycle log 接入与治理测试。
4. 完成启动脚本、README/平台文档并删除死资产引用。
5. 在空模板配置下跑全量自动门禁；只对当前真实可用且获授权的环境执行人工链路。
6. 验证通过后同步 delta specs 并归档；回滚时可移除新增路由/脚本/文档，不涉及 schema migration 或业务数据转换。
