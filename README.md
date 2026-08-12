# 智能 OnCall Agent

本仓库当前提供安全 monorepo 工程基础、SQLite Repository、本地用户认证、tenant 隔离、Qwen provider、只含五个依赖服务的本地 Compose，以及显式连接的 tenant-safe Milvus adapter 基础。完整认证页面、聊天、知识库、AIOps、Agent、RAG 与 MCP 产品能力尚未实现；真实百炼与 Milvus 凭据 smoke 均不属于默认自动化门禁。

## 安装

```bash
npm install
cd apps/backend
uv sync
```

从 `config/*.template.json` 复制被 Git 忽略的本机配置后，可运行各 workspace README 中的命令。

## 验证

```bash
openspec validate --all
docker compose -f infra/compose.yaml config
cd apps/backend && uv run ruff check . && uv run pyright && uv run pytest
cd ../.. && npm run contracts:typecheck && npm run contracts:test
npm run frontend:typecheck && npm run frontend:test && npm run frontend:build
npm run frontend:test:secret
npm run docs:build
git diff --check
```
