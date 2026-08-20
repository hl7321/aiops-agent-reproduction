# 智能 OnCall Agent

本仓库当前提供安全 monorepo 工程基础、SQLite Repository、本地用户认证与中文桌面工作台、tenant 隔离、知识文档/切分、持久索引任务、混合检索、持久流式 Chat Agent、Prompt/Skill/会话记忆，以及 owner-scoped MCP 连接管理、真实工具发现和 Chat 工具注入。`/chat` 已将真实会话 API/SSE、完整检索引用、工具审计摘要、Prompt/Skill 与会话记忆组合为桌面工作区；领域数据仍以服务端为事实来源，不写入 localStorage。Compose 仍只包含五个基础依赖服务；AIOps 与官方 CLS MCP Server 的启动/凭据流程尚未实现。

MCP 连接完整 URL 会由服务端保存并返回，当前不支持自定义 headers。禁止把 token、secret、password 或其他凭据放入 URL query。官方 `cls-mcp-server` 必须在主机运行，不属于 Compose；详见 `docs/runbooks/real-mcp-smoke.md`。

最终 Chat 桌面验证范围和真实服务执行记录见 `docs/runbooks/final-chat-workspace-smoke.md`；未执行的外部服务场景不会被自动化 fake 测试冒充为真实连通。

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
