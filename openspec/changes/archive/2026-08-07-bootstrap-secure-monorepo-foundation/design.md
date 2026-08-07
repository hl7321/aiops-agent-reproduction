## Context

仓库当前只有 OpenSpec 初始化文件，尚无应用结构或历史兼容负担。参见 `proposal.md` 的 Why。本设计必须一次锁定最终技术栈与安全边界，同时保持最小实现，避免把后续产品能力混入 foundation。

## Goals / Non-Goals

**Goals:**

- 建立最终 monorepo 目录、依赖管理方式和统一质量命令。
- 交付最小 FastAPI health app、Vue 桌面 Web、typed contracts 和 VitePress 文档骨架。
- 建立可复用 JSON 深合并与浏览器 public-config allowlist。
- 通过自动化门禁证明导入安全、配置忽略和 secret bundle 隔离。

**Non-Goals:**

- 不实现认证、聊天、知识库、AIOps、tenant 业务、LLM、Agent、Milvus 或 MCP。
- 不创建数据库业务模型、外部服务连接、应用容器或生产部署。
- 不使用 filter-repo、force push 或其他 Git 历史重写流程。

## Decisions

### 1. 使用双生态 monorepo，而不是统一构建工具

根仓库采用 npm workspaces 管理 `apps/frontend`、`packages/api-contracts` 和 `docs`；Python 后端在 `apps/backend` 使用 uv 与 hatchling。最终目录为：

```text
apps/backend
apps/frontend
packages/api-contracts
config
infra
scripts
openspec
docs
```

这样保留每个生态的原生工具和锁文件，根 scripts 只负责编排。未选择 Nx/Turborepo，因为第一阶段没有需要缓存或任务图优化的规模，额外工具会扩大基础维护面。

### 2. 后端锁定 Python/FastAPI 最终栈并保持零副作用导入

后端技术栈固定为 Python >=3.10、FastAPI、Pydantic v2、uv、hatchling 和 `src` layout。包必须位于 `apps/backend/src/super_ai`，项目内只允许 `from super_ai...`，禁止 `from src.super_ai...`。

持久化边界锁定 SQLAlchemy 2 async、aiosqlite 和 Alembic。测试与静态检查使用 pytest、pytest-asyncio、Ruff 和 strict Pyright；pytest 设置 `asyncio_mode=auto`，Ruff 设置 line-length=100、target py310、规则 B/E/F/I/UP。

`create_app()` 只装配最小 `/health`。配置读取与未来数据库、Agent、Milvus、LLM、MCP client 创建都必须通过显式函数或依赖注入进入运行期。模块级代码只定义类型和函数，不进行 I/O 连接。相比模块级全局单例，这使测试能够隔离依赖并保证 import safety。

### 3. 锁定 Agent/AI 依赖，但延后所有能力实现

依赖边界固定为 LangChain 1.x `create_agent`、LangGraph、langchain-openai、langchain-mcp-adapters、MCP、pymilvus 3、rank-bm25、pypdf、langchain-text-splitters 和 httpx。foundation 只在依赖元数据与项目指南中记录这些选择，不创建 Agent graph、provider、collection、tool 或 MCP session。P06 等后续提案再增加 LLM typed validation/provider。

### 4. 前端采用严格 TypeScript 的 Vue 桌面 Web 骨架

前端固定 Vue 3.5、Vite 6、TypeScript 5.6、Pinia 3、Vue Router 4、Vitest 2、marked、DOMPurify 和 lucide-vue-next。TypeScript 启用 strict、exactOptionalPropertyTypes、noUncheckedIndexedAccess、isolatedModules、ES2022 与 Bundler resolution。

验收目标明确为桌面 Web。最小页面只显示配置后的标题与 foundation 状态，不暗示产品功能已经存在。相比预先搭建完整设计系统，这能验证最终构建链同时避免 UI 范围膨胀。

### 5. 运行期 JSON 采用递归深合并，且不以环境变量承载项目配置

Git 只提交 `config/project.template.json` 和 `config/user.project.template.json`，所有 key、secret、password 为空。本机可复制为被忽略的 `project.json` 与 `user.project.json`。后端 `project_config.py` 先读取前者，再用后者递归深合并：对象逐层合并，数组和标量整体覆盖。

加载函数接受显式路径，以便测试使用临时配置。生产默认路径由应用入口显式传入。OS 环境变量不参与项目值解析；仅允许测试/构建工具使用显式函数参数选择临时文件，不把环境变量当成配置字段来源。

### 6. 前端构建侧只投影 public allowlist

浏览器源代码不得直接 import 两份完整 JSON。`vite.config.ts` 调用可测试的 Node 侧 loader 合并配置，再通过 define 注入由 `toPublicConfig()` 返回的对象。allowlist 固定为：

- `frontend.title`
- `frontend.apiBaseUrl`
- 明确标记为 public 的 analytics key

`config.ts` 只暴露对应 typed public config。LLM、CLS、MCP、MinIO 等服务端字段不会被序列化到 define。单元测试使用临时路径验证合并和投影，集成脚本用 sentinel secret 构建并递归扫描 `dist`。相比运行时从后端返回整份配置，该方式在 foundation 阶段更小且能静态证明公开边界。

### 7. 基础设施只保留说明目录

`infra/README.md` 锁定未来 Compose 仅托管 etcd、MinIO、Milvus、Attu、Alertmanager。后端、前端、官方 CLS MCP Server 必须在主机运行。本变更不创建 `app.Dockerfile`、`project.compose.json` 或应用 Compose 服务，避免把应用运行模式与基础设施依赖混在一起。

### 8. 质量门禁和项目指南作为架构的一部分

根 `AGENTS.md` 固化目录、构建命令、Python import/依赖注入、配置/凭据、tenant 预留、真实 MCP、OpenSpec 简体中文和桌面 Web 验收规则。README 只说明骨架和验证方法。

完成条件至少包括 `openspec validate --all`、后端 Ruff/Pyright/pytest、contracts typecheck/test、前端 typecheck/test/build、sentinel 扫描和 `git diff --check`。生成 manifests 后立即运行根 `npm install` 和后端 `uv sync`，提交真实 lockfile。

## Risks / Trade-offs

- [锁定较多未来依赖会增加首次安装时间] → 只锁定明确要求的依赖，不创建使用它们的产品代码，并由 lockfile 保证可重复。
- [Vite 构建配置可能意外序列化完整对象] → 独立 allowlist 投影、类型约束、单元测试和 sentinel bundle 扫描形成多层防护。
- [本机 JSON 缺失导致新开发者无法构建] → 提供空模板和清晰复制说明，测试始终注入临时配置而不依赖真实值。
- [Python 3.10 与较新 AI 包的版本约束可能冲突] → 用 `uv sync` 实际解析并锁定兼容组合，若上游包不支持 Python 3.10 则在不降低 Python 基线的前提下选择兼容版本。
- [跨生态根命令可能掩盖工作目录差异] → 每个 workspace 保留独立命令，根脚本仅使用 npm workspace 转发。

## Migration Plan

这是零项目的首次基础变更，无数据或旧应用迁移。实施顺序为：创建工程 manifests 和测试、安装并生成锁文件、完成最小实现、运行全部门禁、同步 delta spec、归档 change。回滚可通过撤销本 change 的文件提交完成，不涉及数据库或远程服务。
