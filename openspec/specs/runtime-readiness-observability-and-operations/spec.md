# Runtime Readiness Observability and Operations 规格

## Purpose

本能力为智能 OnCall Agent 提供可定位但不泄密的运行时探针、轻量可观测性、本地主机启动流程与最终交付验收，明确区分进程存活、配置有效、依赖可达、自动化门禁和真实外部链路。

## Requirements

### Requirement: 存活探针不得触碰外部依赖
`GET /health` SHALL 只证明 FastAPI 进程能够响应，MUST NOT 读取或连接 SQLite、Milvus、Qwen 或 MCP，也不得初始化 collection、创建外部 client 或启动迁移。

#### Scenario: 外部依赖全部不可用
- **WHEN** SQLite、Milvus、Qwen 与 MCP 均不可用但 FastAPI 进程已启动
- **THEN** `/health` 仍返回 200 的统一成功 envelope，且没有外部连接尝试

### Requirement: 就绪探针逐项报告真实依赖结果
`GET /ready` SHALL 分别执行 SQLite、Milvus、Qwen 和 MCP 的最小真实检查，并为每项返回 `ready|unavailable`、非负 latency 和 nullable 安全错误。所有项成功时返回 200；任一项失败时返回 503，但 MUST 保留其他项的真实结果，MUST NOT 用默认成功或 fake 结果填充。

#### Scenario: 部分依赖失败
- **WHEN** SQLite、Milvus 与 Qwen 检查成功但 MCP 不可达
- **THEN** `/ready` 返回 503，前三项为 ready、MCP 为 unavailable，且错误已脱敏

#### Scenario: 所有依赖可达
- **WHEN** 四项最小真实检查都成功
- **THEN** `/ready` 返回 200 且 overall 状态为 ready

### Requirement: 配置检查区分配置无效与依赖不可达
`GET /config/check` SHALL 先验证显式本地 JSON、必需 section 和字段，再执行与 `/ready` 相同的 SQLite、Milvus、Qwen、MCP 检查。响应 SHALL 包含递归脱敏的 `configuration` 与逐项 `dependencies`；配置无效或依赖不可达均返回 503，但 MUST 以不同 overall 原因明确区分。响应 MUST NOT 包含 password、token、key、secret、authorization 或其值。

#### Scenario: 配置字段缺失
- **WHEN** 本地 JSON 可读取但缺少必需 LLM 字段
- **THEN** `/config/check` 返回 503 和 configuration invalid，且在连接任何依赖前停止

#### Scenario: 配置有效但 Milvus 不可达
- **WHEN** 所有配置 section 有效而 Milvus 检查失败
- **THEN** `/config/check` 返回 503、configuration valid、dependencies unavailable，并保留逐项安全结果

### Requirement: MCP 聚焦探针使用真实连接语义
`GET /health/mcp` SHALL 使用与运行时 MCP 聚合一致的真实 discovery 边界执行聚焦检查。没有配置任何 MCP 来源时 MUST 返回明确 unavailable，不得生成假连接或假工具。

#### Scenario: 未配置 MCP 来源
- **WHEN** 当前运行配置没有可用 MCP 连接来源
- **THEN** `/health/mcp` 返回 503 与安全的未配置说明，且不创建外部 client

### Requirement: 轻量指标使用项目 JSON envelope
`GET /metrics` SHALL 使用当前项目统一 JSON success envelope 返回本进程累计 HTTP 请求数、失败数、总耗时与平均耗时。该 endpoint MUST 明确标识为进程内轻量指标，MUST NOT 使用或声称兼容 Prometheus exposition；指标采集不得记录 header、body 或业务正文。

#### Scenario: 成功与失败请求被计数
- **WHEN** 同一进程已完成成功和失败 HTTP 请求后访问 `/metrics`
- **THEN** 响应中的请求数与失败数包含已完成请求，平均耗时由累计耗时计算且非负

### Requirement: HTTP completion log 可关联且默认脱敏
HTTP middleware SHALL 透传合法 `X-Request-ID` 或生成新值，并为每个完成请求输出一条结构化 JSON log，字段仅包含 requestId、path、status、duration 和固定事件名。递归脱敏 SHALL 覆盖 password、token、key、secret、authorization 及嵌套对象/数组；日志 MUST NOT 记录 headers、body、用户 query/prompt、工具参数值或输出、模型正文和凭据。

#### Scenario: 请求携带敏感内容
- **WHEN** 请求 header、body 或异常包含 token、password 与嵌套 secret
- **THEN** completion log 仍只包含允许字段，其他安全日志中的敏感值统一为 `[redacted]`

### Requirement: 关键运行时 lifecycle 只记录安全摘要
文档索引、Chat、MCP、AIOps 和后台任务 SHALL 记录可关联的 lifecycle log 或持久审计，允许字段仅为资源 ID、request ID、状态、错误分类、耗时、工具名和参数键。MUST NOT 复制用户正文、完整参数、工具输出、模型正文或凭据。

#### Scenario: 工具调用失败
- **WHEN** MCP 或 Agent 工具调用失败且参数包含 query 与 authorization
- **THEN** lifecycle 记录只包含工具名、参数键、失败状态、分类与耗时，不包含任一参数值

### Requirement: 本地启动脚本保持应用主机运行边界
仓库 SHALL 提供 `scripts/start-local.sh` 与 `scripts/start-local.bat`。脚本 SHALL 显式检查依赖并在缺失时给出可执行提示，启动五服务 Compose、执行 `uv sync` 和 Alembic upgrade，再在主机启动官方 CLS MCP、uvicorn app factory 与 Vite；日志写入 ignored `apps/backend/var`。脚本 MAY 把本地 JSON 的 CLS 凭据转换为官方 CLS MCP 子进程环境，但应用自身 MUST NOT 从环境变量读取项目配置。

#### Scenario: Unix 脚本语法检查
- **WHEN** 开发者在 macOS、Linux 或 Git Bash 执行 `bash -n scripts/start-local.sh`
- **THEN** 脚本语法有效，且运行流程不创建应用 Compose 服务

#### Scenario: Windows 原生启动
- **WHEN** 开发者在安装了前置依赖的 Windows cmd 或 PowerShell 中显式运行 `start-local.bat`
- **THEN** 脚本不依赖 Bash，并在主机启动应用进程与官方 CLS MCP

### Requirement: 普通启动与真实 fixture 副作用分离
普通应用启动、自动测试与配置检查 MUST NOT 上传 CLS 日志、发布告警或 seed SOP。文档 SHALL 把这些 fixture 命令列为用户确认目标后显式执行的外部副作用，并说明失败退出与脱敏边界。

#### Scenario: 执行普通本地启动
- **WHEN** 开发者运行任一本地启动脚本
- **THEN** 基础设施和主机应用被启动，但没有自动运行 P25 的日志上传、告警发布或 SOP seed

### Requirement: 最终验收诚实区分自动与真实链路
fresh clone SHALL 能从无秘密模板创建 ignored 本地 JSON，并通过 OpenSpec、contracts、backend、frontend、Compose、脚本语法和 Git whitespace 自动门禁；自动测试 MUST 使用临时配置和可注入外部边界。真实桌面链路 SHALL 仅在用户提供有效凭据与明确目标后执行，缺失环境时必须逐项记录未执行，MUST NOT 把 fake test 描述为真实连通性通过。

#### Scenario: 无真实 secret 的 fresh clone
- **WHEN** 开发者从模板复制空本机配置并运行全部自动门禁
- **THEN** 门禁不要求提交或提供真实 Qwen、Milvus、MCP 或 CLS 凭据即可通过

#### Scenario: 真实环境不完整
- **WHEN** Qwen、Milvus、官方 CLS MCP、CLS 或 Alertmanager 任一真实目标不可用
- **THEN** 交付记录列出对应人工链路未执行，不生成假验收结论
