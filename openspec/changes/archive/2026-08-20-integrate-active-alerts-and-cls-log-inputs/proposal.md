## Why

P21 的 AIOps 诊断需要可追溯的真实告警与日志输入，但当前项目只有 Alertmanager 容器和 CLS MCP 配置边界，没有统一的活跃告警读取合同，也没有与应用运行时隔离的安全 CLS 日志上传工具。现在需要先建立只负责输入、不生成诊断结论的稳定边界，并从设计上阻止测试或启动过程意外写入用户的 CLS。

## What Changes

- 增加 deployment-global `prometheusAlerts.sources` typed 配置，支持 `prometheus-v1`、`alertmanager-v2`、可选 Basic Auth 与有界 timeout；凭据继续只保存在被忽略的本机 JSON。
- 增加异步 AlertProvider/Aggregator，通过真实 HTTP API 并发读取、标准化和确定性返回活跃告警；允许单源失败降级，但零源或全部失败必须返回安全 503。
- 增加 bearer-protected `GET /aiops/alerts/active`，仅返回标准化 items，不暴露虚构的 provider 状态集合。
- 扩展共享 contracts、Pydantic 与机器可读 OpenAPI，统一告警 source/status/rawContext 和共享错误目录。
- 增加独立 `scripts/generate_and_upload_cls_logs.py`，从本地 JSON 深合并配置读取 CLS 凭据，生成有界无敏感结构化日志，并仅在人工显式执行时通过官方 SDK 上传。
- 明确真实 CLS 写入必须在用户确认 endpoint/topic 目标后执行；import、测试、应用启动与普通运行绝不触发上传。
- 本 change 不持久化告警、不创建 user-owned source，也不生成诊断、报告或处置建议；这些由 P21 消费本提案输入后实现。

## Capabilities

### New Capabilities

- `active-alert-and-cls-log-inputs`: 定义多来源活跃告警聚合、认证读取 API，以及独立 CLS 日志生成与显式上传的安全行为。

### Modified Capabilities

- `api-and-sse-contracts`: 增加标准告警 DTO、稳定全源不可用错误与 `/aiops/alerts/active` 的 bearer-protected OpenAPI 合同。

## Impact

- 后端新增 `super_ai.alerts` 配置、provider、aggregator、依赖与路由模块，并扩展配置化 app factory。
- `packages/api-contracts` 增加告警类型、错误码与 OpenAPI path；后端 Pydantic/manifest 合同同步。
- `config/project.template.json` 与 `config/user.project.template.json` 调整告警 sources 和 CLS 人工关联配置，所有 secret/password 保持空值。
- 独立脚本通过 PEP 723 元数据与单独 lock 使用官方 `tencentcloud-cls-sdk-python`；不把其旧 protobuf 依赖混入使用 pymilvus 3 的 backend 环境，SDK client 只在脚本显式执行路径创建。
- `scripts` 与中文运行说明增加安全日志生成/上传入口；自动化仅使用 fake HTTP/SDK，不访问真实 Prometheus、Alertmanager 或 CLS。
