## Why

平台的产品能力已经形成完整链路，但仍缺少统一的运行时就绪判断、可安全定位故障的轻量可观测性，以及可复现的本地主机启动与交付说明。P26 需要把这些边界补齐，形成不依赖真实凭据也能执行的最终自动门禁，同时诚实区分自动化验证与真实外部服务验收。

## What Changes

- 新增进程存活、依赖就绪、配置检查、MCP 聚焦诊断和本进程轻量指标探针；依赖失败保留逐项安全结果并返回 503。
- 为所有 HTTP 请求生成或透传 request ID，记录不含请求内容与凭据的结构化 completion log，并统一递归脱敏与关键运行时 lifecycle 日志字段。
- 提供 macOS/Linux/Git Bash 与 Windows 本地主机启动脚本，顺序启动五服务基础设施、迁移、官方 CLS MCP、FastAPI 与 Vite，日志写入 ignored 后端 var 目录。
- 更新中文 README、各平台安装指南、运维监控说明和真实日志/告警教程，明确普通启动与真实 fixture 外部副作用分离。
- 清理应用 Dockerfile、`project.compose.json`、`create_compose_app` 及其死引用，保持应用只在主机运行。
- 建立 fresh-clone、无真实 secret 可通过的最终自动门禁，并单独记录需要真实 Qwen、Milvus、CLS MCP、CLS 和告警目标的桌面人工链路结果。

## Capabilities

### New Capabilities

- `runtime-readiness-observability-and-operations`：定义运行时探针、轻量指标、安全日志、本地启动、平台文档和最终交付验收边界。

### Modified Capabilities

- `monorepo-foundation`：把主机启动、最终文档、废弃应用容器资产清理与完整质量门禁提升为交付要求。
- `api-and-sse-contracts`：在机器可读合同中登记 `/ready`、`/config/check`、`/health/mcp` 与 `/metrics` 的统一 envelope 路径和 DTO。

## Impact

- 后端应用工厂、运行时检查、配置验证、请求中间件、安全日志与生命周期日志。
- `packages/api-contracts` 的运行时 DTO、typed entrypoint、manifest 与合同测试。
- `scripts/start-local.sh`、`scripts/start-local.bat`、根 README、VitePress 文档与仓库治理测试。
- 本地 SQLite、Milvus、Qwen、MCP 和五服务 Compose；自动测试继续使用临时配置与注入式外部边界，不触发真实 fixture 副作用。
