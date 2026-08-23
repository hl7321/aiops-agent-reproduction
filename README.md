# 智能 OnCall Agent

这是一个本地优先、OpenSpec 驱动的智能 OnCall Agent monorepo。当前已实现：本地认证与 tenant 隔离、SQLite/Alembic 持久化、持久后台任务、知识文档上传/切分/Qwen embedding/Milvus 索引、BM25L + 向量 + Qwen rerank 检索、持久 SSE Chat Agent、Prompt/渐进式 Skill、会话记忆、真实 MCP 连接与工具审计、Prometheus/Alertmanager 活跃告警、LangGraph AIOps 诊断/证据/报告/案例、结构化反馈，以及 10 套关联式 Java 电商 fixtures。外部能力只有在本机配置真实凭据并启动对应服务后才可连通。

## 目录

- `apps/backend`：FastAPI、SQLite Repository、Agent/AIOps 运行时。
- `apps/frontend`：Vue 3 中文桌面工作台（`/chat`、`/knowledge`、`/aiops`、`/mcp`）。
- `packages/api-contracts`：HTTP、OpenAPI 与 SSE 单一事实来源。
- `config`：可提交空模板与 ignored 本机 JSON。
- `infra`：仅 etcd、MinIO、Milvus、Attu、Alertmanager 五服务 Compose。
- `scripts`：本地启动与需要显式执行的 fixtures。
- `openspec`：主规格与归档 change。
- `docs`：VitePress WIKI、OpenSpec 导航、安装、运维、教程与 runbook。

## OpenSpec WIKI

`docs/openspec` 是指向仓库 `openspec` 的相对符号链接；WIKI 通过 VitePress include 展示原始 artifacts，不复制正文。创建 active change 后运行 `uv run --project apps/backend python scripts/sync_wiki.py active`，归档后运行 `uv run --project apps/backend python scripts/sync_wiki.py archive --change <change-name>`；全量重建使用 `uv run --project apps/backend python scripts/sync_wiki.py all`。

```bash
uv run --project apps/backend python scripts/sync_wiki.py audit-includes
uv run --project apps/backend python scripts/sync_wiki.py audit-counts
npm run docs:dev
npm run docs:build
npm run docs:preview
```

Windows checkout 必须先启用 Developer Mode 和 Git symlink 支持，不能复制 `openspec` 目录作为 fallback。具体检查见 `docs/setup/windows.md`。

## 配置

```bash
cp config/project.template.json config/project.json
cp config/user.project.template.json config/user.project.json
```

只在被 Git 忽略的 `config/user.project.json` 填写 Qwen、CLS 等个人凭据。后端只读取两份本地 JSON 的递归深合并结果；浏览器 bundle 只接收公开 allowlist。不要把 token/secret 放进 MCP URL query，也不要提交本机 JSON。

## 启动

macOS、Linux 或 Git Bash：

```bash
./scripts/start-local.sh
```

Windows cmd 或 PowerShell：

```bat
scripts\start-local.bat
```

脚本启动五服务 Compose，执行 `uv sync` 与 Alembic migration，再在主机启动官方 CLS MCP（仅凭据齐备时）、FastAPI 与 Vite。日志写入 ignored 的 `apps/backend/var`。普通启动不会上传 CLS 日志、发布告警或 seed SOP。

访问地址：

- 前端：http://127.0.0.1:5173
- 后端/OpenAPI：http://127.0.0.1:8000 / http://127.0.0.1:8000/docs
- 存活/就绪/配置/指标：`/health`、`/ready`、`/config/check`、`/metrics`
- Attu / Alertmanager：http://127.0.0.1:3001 / http://127.0.0.1:9093

各平台前置安装见 `docs/setup/`；手动分步启动见 `docs/operations-and-monitoring.md`。

## 全量验证

```bash
openspec validate --all
npm run contracts:typecheck
npm run contracts:test
cd apps/backend
uv sync
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest
cd ../..
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
npm run docs:build
uv run --project apps/backend python scripts/sync_wiki.py audit-includes
uv run --project apps/backend python scripts/sync_wiki.py audit-counts
docker compose -f infra/compose.yaml config
bash -n scripts/start-local.sh
git diff --check
```

Windows 的 `start-local.bat` 必须在真实 cmd/PowerShell 验证，不能用 Bash 代替。自动测试使用临时配置和注入式外部边界，只证明代码合同；真实 Qwen/Milvus/CLS MCP/CLS/Alertmanager 桌面链路需具备环境后人工执行并如实记录。

真实 fixture 的副作用与顺序见 `docs/tutorials/real-log-and-alert.md`。OpenSpec 文档使用简体中文，提交遵循 Conventional Commits。
