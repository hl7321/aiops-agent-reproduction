# 安全 Monorepo 基础设计

日期：2026-08-07  
OpenSpec change：`bootstrap-secure-monorepo-foundation`

## 目标

本变更是智能 OnCall Agent 项目的首个基础提案。它只建立最终技术栈、目录骨架、工程边界、安全配置边界和质量门禁，不实现认证、聊天、知识库、AIOps、MCP 或其他产品能力。

完成后，仓库必须能够安装依赖、运行最小后端健康检查、构建桌面 Web 前端、校验共享类型，并通过自动化测试证明模块导入安全以及浏览器 bundle 不包含服务端秘密。

## 技术栈

### 后端

- Python 3.10 或更高版本。
- FastAPI、Pydantic v2。
- uv 管理依赖和锁文件，hatchling 构建，采用 `src` layout。
- SQLAlchemy 2 async、aiosqlite、Alembic 作为未来持久化基础，但本变更不建立业务模型或导入时连接。
- pytest、pytest-asyncio，`asyncio_mode=auto`。
- Ruff：行长 100、目标 Python 3.10、启用 B/E/F/I/UP。
- strict Pyright。

后端包固定为 `apps/backend/src/super_ai`。项目代码只允许 `from super_ai...`，禁止 `from src.super_ai...`。

### Agent 与 AI 依赖边界

锁定 LangChain 1.x `create_agent`、LangGraph、langchain-openai、langchain-mcp-adapters、MCP、pymilvus 3、rank-bm25、pypdf、langchain-text-splitters 和 httpx。它们仅作为后续提案的技术边界，本变更不创建 Agent、LLM、Milvus 或 MCP 产品功能。

### 前端

- Vue 3.5、Vite 6、TypeScript 5.6。
- TypeScript 使用 strict、`exactOptionalPropertyTypes`、`noUncheckedIndexedAccess`、`isolatedModules`、ES2022 和 Bundler resolution。
- Pinia 3、Vue Router 4、Vitest 2。
- marked、DOMPurify、lucide-vue-next 作为后续界面能力依赖。
- 验收目标为桌面 Web，不承诺移动端体验。

### 仓库

- npm workspaces 管理前端、API contracts 和 VitePress 文档。
- OpenSpec 使用 spec-driven workflow，所有 OpenSpec 文档使用简体中文。
- 提交信息使用 Conventional Commits。

## 最终目录与边界

```text
apps/
  backend/
  frontend/
packages/
  api-contracts/
config/
infra/
scripts/
openspec/
docs/
```

根 npm workspaces 管理 `apps/frontend`、`packages/api-contracts` 和 `docs`。Python 后端由自身的 `pyproject.toml` 与 `uv.lock` 管理。共享 API contracts 只提供最小 foundation 类型，不提前定义未来业务协议。

## 后端架构

`super_ai` 提供显式 `create_app()`。最小应用只注册 `/health`，返回稳定、可测试的健康状态。模块导入只定义类型、函数和路由，不读取外部服务、不连接 SQLite、Milvus、LLM 或 MCP。

通用 JSON 配置加载器位于 `project_config.py`：先读取 `config/project.json`，再用 `config/user.project.json` 做递归深合并。加载器接受显式路径以支持测试注入；应用入口负责在运行期传入项目路径。OS 环境变量不作为项目配置来源。

数据库、Agent 和外部服务依赖只能在未来提案中通过显式工厂或 FastAPI 依赖注入创建，不能成为模块级单例连接。

## 前端公开配置边界

两份完整 JSON 只能由构建侧读取，浏览器源代码不得直接导入。Vite 构建配置调用一个可测试的深合并 loader，并将结果投影到明确 allowlist：

- `frontend.title`
- `frontend.apiBaseUrl`
- 明确标记为 public 的 analytics key

浏览器端 `config.ts` 只消费投影后的 typed public config。LLM、CLS、MCP、MinIO 等秘密字段即使存在于本机 JSON，也不得进入 Vite define、虚拟模块或最终 bundle。

测试用显式临时路径注入配置。集成门禁使用 sentinel secret 完成一次构建并扫描 `dist`，确认 sentinel 不存在。开发构建可从模板复制被 Git 忽略的空本机配置，但这些文件不能暂存。

## 配置与凭据

Git 只提交：

- `config/project.template.json`
- `config/user.project.template.json`

所有 key、secret 和 password 默认值必须为空。`.gitignore` 忽略真实本机配置、`.env*`、IDE 文件、虚拟环境、依赖、构建产物、覆盖率、缓存、后端 var、SQLite 和日志。

项目从零开始，不设计或执行 filter-repo、force push 等历史重写流程。

## 基础设施边界

本变更只创建 `infra/` 及说明文档。未来 Compose 只允许托管 etcd、MinIO、Milvus、Attu 和 Alertmanager。后端、前端、官方 CLS MCP Server 必须在主机运行。本变更不创建应用 Dockerfile、`project.compose.json` 或应用 Compose 服务。

## 测试和质量门禁

最小测试覆盖：

- 最终目录存在。
- Python 包导入路径正确。
- 根和 workspace scripts 存在。
- 敏感配置、缓存和产物被忽略。
- 导入 `super_ai` 不建立外部连接。
- 后端 JSON 配置递归深合并。
- 前端 public config allowlist。
- sentinel secret 不出现在构建产物。

必须执行并通过：

```text
openspec validate --all
cd apps/backend && uv run ruff check .
cd apps/backend && uv run pyright
cd apps/backend && uv run pytest
npm run contracts:typecheck
npm run contracts:test
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
git diff --check
```

生成根 `package.json` 和后端 `pyproject.toml` 后，必须先运行根 `npm install` 与后端 `uv sync`，生成并验证真实锁文件。任何门禁失败都先修复并重新运行，全部通过后才能同步 delta specs 和归档。

## 非目标

- 不实现认证、权限、tenant 业务逻辑或用户体系。
- 不实现聊天、知识库、检索、AIOps、Agent、LLM、MCP、Milvus 或告警业务。
- 不运行应用容器，也不创建应用 Dockerfile。
- 不声称 README 中未实现的能力已经可用。
- 不重写 Git 历史。

## 验收结果

验收成功意味着仓库具有可安装、可运行、可测试的最终基础骨架和安全边界；只证明 foundation 已建立，不代表任何产品功能已经交付。
