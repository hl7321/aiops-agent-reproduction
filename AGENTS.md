# 项目协作指南

## 项目边界

本仓库是智能 OnCall Agent 的 monorepo。当前 foundation 只提供工程骨架，不代表认证、聊天、知识库、AIOps、Agent、LLM、Milvus 或 MCP 产品功能已经实现。

最终目录固定为：

- `apps/backend`：Python/FastAPI 后端。
- `apps/frontend`：Vue 桌面 Web 前端。
- `packages/api-contracts`：前后端共享的 TypeScript contracts。
- `config`：可提交模板与被忽略的本机 JSON 配置。
- `infra`：基础设施边界说明；不放置应用容器。
- `scripts`：仓库维护脚本和使用说明。
- `openspec`：spec-driven 规格与变更。
- `docs`：VitePress 文档。

## 技术栈

后端使用 Python >=3.10、FastAPI、Pydantic v2、uv、hatchling、src layout、SQLAlchemy 2 async、aiosqlite、Alembic、pytest、pytest-asyncio、Ruff 和 strict Pyright。pytest 使用 `asyncio_mode=auto`；Ruff 使用 line-length=100、target py310、规则 B/E/F/I/UP。

Agent/AI 依赖边界锁定 LangChain 1.x `create_agent`、LangGraph、langchain-openai、langchain-mcp-adapters、MCP、pymilvus 3、rank-bm25、pypdf、langchain-text-splitters 和 httpx。这些能力由后续 OpenSpec change 实现。

前端使用 Vue 3.5、Vite 6、TypeScript 5.6 strict、Pinia 3、Vue Router 4、Vitest 2、marked、DOMPurify 和 lucide-vue-next。TypeScript 必须启用 exactOptionalPropertyTypes、noUncheckedIndexedAccess、isolatedModules、ES2022 与 Bundler resolution。验收目标是桌面 Web。

## 常用命令

```bash
npm install
npm run contracts:typecheck
npm run contracts:test
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
npm run frontend:test:secret
npm run docs:build

cd apps/backend
uv sync
uv run ruff check .
uv run pyright
uv run pytest

cd ../..
openspec validate --all
git diff --check
```

## Python import 与依赖注入

- 后端包必须位于 `apps/backend/src/super_ai`。
- 只允许 `from super_ai...`，禁止 `from src.super_ai...`。
- 模块 import 期间不得连接 SQLite、Milvus、LLM 或 MCP，也不得创建有 I/O 副作用的全局 client。
- 数据库 session、LLM、Milvus 和 MCP client 必须由显式工厂或 FastAPI 依赖注入在运行期创建。

## 配置与凭据

- Git 只提交 `config/project.template.json` 与 `config/user.project.template.json`。
- 本机使用被忽略的 `config/project.json` 和 `config/user.project.json`。
- 应用先读取 project 配置，再用 user 配置递归深合并；不得把 OS 环境变量作为项目配置来源。
- 所有 key、secret、password 模板值必须为空。测试使用临时配置注入，不依赖开发者真实值。
- 前端不得 import 完整 JSON。构建侧只允许公开 `frontend.title`、`frontend.apiBaseUrl` 和明确 public 的 analytics key。LLM、CLS、MCP、MinIO secret 永远不得进入浏览器 bundle。

## Tenant 与外部服务

- foundation 不实现 tenant 行为；后续数据模型和接口必须显式携带 tenant 边界，禁止依赖隐式全局 tenant。
- MCP 集成必须连接真实、受支持的 MCP Server；测试可使用进程内可控替身，但不得用假接口冒充生产集成。
- 未来 Compose 只托管 etcd、MinIO、Milvus、Attu、Alertmanager。后端、前端和官方 CLS MCP Server 在主机运行。
- 禁止创建应用 `app.Dockerfile`、`project.compose.json` 或应用 Compose 服务。

## OpenSpec 与验收

- 所有 proposal、design、spec、tasks 使用简体中文。
- 先更新规格和任务，再实施；实现完成后必须使用 `$openspec-verify-change` 检查完整性、正确性与设计一致性。
- `openspec-verify-change` 不能替代工程门禁；修复其 CRITICAL 问题并处理 WARNING 后，仍须运行完整门禁，才能同步 delta specs 并归档。
- 前端以桌面 Web 布局和交互作为验收目标；README 不得声称未实现的产品能力。
- 使用 Conventional Commits；从零项目不设计 filter-repo 或 force push。
