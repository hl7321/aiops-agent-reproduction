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

## 第一次运行（照着做五步）

### 1. 前置依赖

| 需要什么 | 说明 |
|---|---|
| Docker Desktop | 必须**先打开**，五服务 Compose（etcd / MinIO / Milvus / Attu / Alertmanager）跑在容器里；镜像由 `infra/compose.yaml` 固定版本，仓库不发布、也不需要预拉 |
| Node.js 20+ 与 npm | 前端工作台与官方 CLS MCP |
| uv | 后端依赖与虚拟环境（Python 3.10+） |
| npx | 以 `npx -y cls-mcp-server@latest` 在主机启动官方腾讯云 CLS MCP（**不进 Compose**） |

各平台细节见 `docs/setup/macos.md`、`docs/setup/linux.md`、`docs/setup/windows.md`。

### 2. 生成两份本地配置

```bash
cp config/project.template.json config/project.json
cp config/user.project.template.json config/user.project.json
```

两份文件都在 `.gitignore` 里，**永远不会被提交**。模板里的密钥字段是空的，程序只读这两份本地 JSON 的递归深合并结果，不从环境变量补取凭据。

### 3. 填凭据（不填也能启动，但对应能力会明确报 unavailable）

写在 `config/user.project.json`（这是唯一的密钥落点）：

| 字段 | 用途 | 不填的后果 |
|---|---|---|
| `llm.chat.apiKey` | 聊天模型（默认 DeepSeek 端点） | 聊天与 AIOps 诊断不可用 |
| `llm.apiKey` | embedding 与 rerank（百炼） | 知识库上传/检索不可用 |
| `clsMcpServer.secretId` / `secretKey` | 官方 CLS MCP 的真实日志工具 | `/ready` 的 mcp 显示 unavailable |
| `clsLogUpload.*` | 上传示例日志用的日志集/主题 | 只有跑示例 fixtures 时才需要 |
| `aiopsDemo.email` / `password` | 演示账号（可选） | 只有示例脚本需要 |

`config/project.json` 放非密钥的默认值（模型名、端点、端口）。要换模型时，改 `llm.chat.model` 和 `modelCapabilities` 里**同名**的 `contextWindowTokens` 两处，换厂商再加 `llm.chat.baseUrl`。规则详见 `docs/architecture/model-providers.md`。

不要把 token/secret 放进 MCP URL query，也不要提交这两份本机 JSON。

### 4. 启动

一条命令会启动五服务 Compose、`uv sync`、Alembic 迁移、官方 CLS MCP（仅凭据齐备时）、FastAPI 与 Vite。

macOS、Linux 或 Git Bash：

```bash
./scripts/start-local.sh
```

Windows cmd 或 PowerShell：

```bat
scripts\start-local.bat
```

日志写入 ignored 的 `apps/backend/var`。普通启动不会上传 CLS 日志、发布告警或 seed SOP；这些是需要显式执行的 fixtures，见 `docs/tutorials/real-log-and-alert.md`。

访问地址：

- 前端：http://127.0.0.1:5173
- 后端/OpenAPI：http://127.0.0.1:8000 / http://127.0.0.1:8000/docs
- 存活/就绪/配置/指标：`/health`、`/ready`、`/config/check`、`/metrics`
- Attu / Alertmanager：http://127.0.0.1:3000 / http://127.0.0.1:9093
- 官方 CLS MCP（主机进程，不是容器）：http://127.0.0.1:3001/mcp —— 端口固定 3001，3000 归 Attu

### 5. 验证跑起来了

```bash
curl -s http://127.0.0.1:8000/ready
```

`ok: true` 且 `sqlite` / `milvus` / `qwen` / `mcp` 四项都 ready，就说明这一轮启动是完整的。

其中 `qwen` 这一项实际探测的是**聊天模型**（可能是 DeepSeek 等任何 OpenAI-compatible 端点），
`milvus` 依赖 embedding 凭据。**没有填对应凭据时这两项会显示 unavailable 并给出原因，这是如实报告，不是崩溃**：
页面能打开、能注册登录，但没有凭据的聊天/检索/诊断不会假装成功。

各平台前置安装见 `docs/setup/`；手动分步启动与故障排查见 `docs/operations-and-monitoring.md`。

> **开着系统代理的 macOS 用户注意**：ClashX、Surge 之类的代理会把 `127.0.0.1` 的请求也转发出去，
> 表现为后端日志里连的是代理端口（例如 7890），MCP 一直连不上而 `/ready` 报 `mcp: unavailable`。
> 启动后端前加一次环境变量即可绕开：`NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost"`。
> 官方 CLS MCP 与 Attu 的端口是 3001 / 3000，两者不能互换。

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

## 许可证

MIT，见 [LICENSE](./LICENSE)。
