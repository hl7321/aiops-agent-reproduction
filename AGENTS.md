# 项目协作指南

## 项目边界

本仓库是智能 OnCall Agent 的 monorepo。当前已提供工程骨架、SQLite Repository、本地认证、中文桌面认证工作台壳、模型 provider、五服务本地基础设施和 tenant-safe Milvus adapter 基础；这不代表聊天、知识库、AIOps、Agent、RAG 或 MCP 产品功能已经实现。

最终目录固定为：

- `apps/backend`：Python/FastAPI 后端。
- `apps/frontend`：Vue 桌面 Web 前端。
- `packages/api-contracts`：前后端共享的 TypeScript contracts。
- `config`：可提交模板与被忽略的本机 JSON 配置。
- `infra`：只托管五个基础服务的 Compose 与运行说明；不放置应用容器。
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
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest

cd ../..
docker compose -f infra/compose.yaml config
openspec validate --all
git diff --check
```

## Python import 与依赖注入

- 后端包必须位于 `apps/backend/src/super_ai`。
- 只允许 `from super_ai...`，禁止 `from src.super_ai...`。
- 模块 import 期间不得连接 SQLite、Milvus、LLM 或 MCP，也不得创建有 I/O 副作用的全局 client。
- 数据库 session、LLM、Milvus 和 MCP client 必须由显式工厂或 FastAPI 依赖注入在运行期创建。
- Alembic 是数据库 schema 迁移的唯一权威；应用启动和运行时代码禁止用 `metadata.create_all` 代替迁移。
- 领域服务依赖 Repository Protocol 与不可变 record，不得接收 ORM model 或 `AsyncSession`；SQLite adapter 只能位于 `super_ai.memory.sqlite` 或 `super_ai.memory.extended_sqlite`。
- 每个事务 scope 使用独立 async session，正常退出提交、异常回滚并关闭；测试只能使用 `tmp_path` 下的临时 SQLite 文件。
- 需要查询、唯一性、外键或关联的数据必须使用规范化列和表，禁止塞入无结构的大 JSON 字段。

## 配置与凭据

- Git 只提交 `config/project.template.json` 与 `config/user.project.template.json`。
- 本机使用被忽略的 `config/project.json` 和 `config/user.project.json`。
- 应用先读取 project 配置，再用 user 配置递归深合并；不得把 OS 环境变量作为项目配置来源。
- 数据库 URL 位于合并后的 `database.url`；迁移、lifespan、依赖 provider 和显式初始化路径遵守同一配置来源。
- 所有 key、secret、password 模板值必须为空。测试使用临时配置注入，不依赖开发者真实值。
- 前端不得 import 完整 JSON。构建侧只允许公开 `frontend.title`、`frontend.apiBaseUrl` 和明确 public 的 analytics key。LLM、CLS、MCP、MinIO secret 永远不得进入浏览器 bundle。

## Tenant 与外部服务

- 当前本地模型把认证 `user_id` 同时作为 `tenant_id` 与 `owner_user_id`，但代码、合同和向量 metadata 必须保留 tenant/owner 两个语义字段。
- 所有受保护 Repository 方法必须把 `owner_user_id` 作为首个业务参数；SQLite 查询、更新、删除和父子资源访问必须在同一 SQL 语句中包含 owner scope，禁止先按资源 ID 查询再在 service 层补检查。
- 直接资源不存在与跨 owner 访问统一使用不可枚举 404；受保护父资源不可见统一使用 `AUTH_FORBIDDEN` 403，禁止用第二次无 scope 查询探测存在性。
- Milvus 搜索 filter 只能使用 `tenantId + allowedKnowledgeBaseIds`；空 KB 列表必须在连接 Milvus 前返回空结果。可选 document/metadata 条件在 scoped 召回后执行。
- 向量 metadata 同时写 `tenantId` 与 `ownerUserId`。删除向量必须包含非空 `tenantId + knowledgeBaseId + documentId`，禁止空 scope 或宽删除。
- Chat、Knowledge、Index Jobs、Vector、MCP、AIOps、Evidence、Reports、Cases、Feedback、Audit 和 Background Jobs 都必须显式接收 CurrentUser/OwnerScope，禁止隐式全局 tenant。
- logout 只撤销认证 session 并清理客户端可见状态，不得删除用户持久数据。
- MCP 集成必须连接真实、受支持的 MCP Server；测试可使用进程内可控替身，但不得用假接口冒充生产集成。
- `infra/compose.yaml` 只托管 etcd、MinIO、Milvus、Attu、Alertmanager，并且是五个镜像版本的唯一事实来源。后端、前端和官方 CLS MCP Server 在主机运行。
- MinIO 只作为 Milvus standalone 的内部依赖，不是应用文档对象存储；禁止在 Compose 中加入日志上传、SOP seed、`env_file` 或变量插值。
- 禁止创建应用 `app.Dockerfile`、`project.compose.json` 或应用 Compose 服务。

## Milvus Adapter 边界

- `super_ai.vector_store` 只消费本地 JSON 深合并后的 typed `vectorStore`；禁止从 OS 环境变量补充 URI、token 或 collection。
- client 只能由显式 `connect()`/`initialize()` 创建；模块 import、应用加载和空 KB search 不得创建 client 或连接网络。
- collection 固定 1024 维 FLOAT_VECTOR、HNSW/COSINE、M=16、efConstruction=200，search ef=64；tenantId、knowledgeBaseId、documentId 建立标量索引。
- insert 必须同时保存 tenantId/ownerUserId 标量与可信 metadata；search filter 只能包含 tenantId + allowed KB；delete 必须包含 tenantId + KB + document。
- PyMilvus 同步调用必须移出 async 事件循环。当前官方 client 没有稳定 public close 合同，禁止虚构 `close()`。
- 自动化测试使用 fake client；真实 Milvus smoke 只有在本机服务与 ignored JSON 凭据可用时人工执行，未执行不得声称连通性通过。

## 模型 Provider 边界

- Qwen/百炼配置只能来自 `project.json` 与 `user.project.json` 的深合并结果；禁止从 `OPENAI_API_KEY`、`DASHSCOPE_API_KEY` 等 OS 环境变量读取项目配置。
- Chat 只通过 `langchain-openai` 的 `ChatOpenAI`，Embedding 只通过 `OpenAIEmbeddings`；Rerank 使用独立可注入 `httpx.AsyncClient`。禁止引入 DashScope SDK。
- 默认 Chat 为 `qwen3.7-max`、temperature 0.2、timeout 120 秒、max retries 2，并必须有 `contextWindowTokens` profile。
- Embedding 使用 `text-embedding-v4`、1024 维、`check_embedding_ctx_length=false`，单批和 chunk size 不得超过 10，跨批必须保持输入顺序。
- Rerank 使用 `qwen3-vl-rerank` 的真实 HTTP 分数，禁止生成 fallback 分数。所有 provider/readiness 异常中的当前 API key 必须替换为 `[redacted]`。
- 模型 client 只在显式 factory/调用路径创建；import、应用模块加载和测试收集期间不得读取真实配置或联网。真实凭据 smoke 是人工步骤，未执行不得声称连通性通过。

## OpenSpec 与验收

- 所有 proposal、design、spec、tasks 使用简体中文。
- 先更新规格和任务，再实施；实现完成后必须使用 `$openspec-verify-change` 检查完整性、正确性与设计一致性。
- `openspec-verify-change` 不能替代工程门禁；修复其 CRITICAL 问题并处理 WARNING 后，仍须运行完整门禁，才能同步 delta specs 并归档。
- 前端以桌面 Web 布局和交互作为验收目标；README 不得声称未实现的产品能力。
- 使用 Conventional Commits；从零项目不设计 filter-repo 或 force push。
