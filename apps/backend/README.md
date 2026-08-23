# 后端工程基础

本 workspace 提供 FastAPI app factory、使用统一成功 envelope 的 `/health`、request ID 中间件、统一错误/验证/异常响应，以及通用 JSON 配置深合并。Pydantic 合同镜像由测试与 `packages/api-contracts/contract-manifest.json` 对齐。

持久化 foundation 已提供 SQLAlchemy 2 async runtime、Alembic migration、事务 scope、Repository Protocol、不可变 record 和 SQLite adapter 扩展边界。Alembic 是 schema 唯一权威；应用不会在导入或默认启动时连接数据库、自动迁移或调用 `metadata.create_all`。测试只使用 pytest 临时 SQLite 文件。

当前已实现本地认证、owner-scoped 文档管理、durable 文档索引、混合检索 Tool、持久流式 Chat Agent，以及 owner-scoped MCP connection CRUD/check。Chat 每轮只装配当前用户 enabled 连接的真实 MCP tools；没有 enabled 连接时才可使用本地 JSON 中非空的 CLS 回退地址。工具发现失败和同名冲突显式失败，真实工具调用不自动重试，避免重复外部副作用。

MCP 产品运行时使用 `langchain-mcp-adapters`，不包含假 profile、静态工具目录或假调用结果。自动化测试的 injected fake client 只验证边界，不代表官方 CLS MCP 已连通。完整 URL 会持久化并返回；禁止在 URL query 放置凭据。官方主机服务启动与凭据边界见根 README 和 `docs/setup/`。

AIOps 已提供真实告警聚合、durable LangGraph 诊断、证据链、报告、案例沉淀和反馈 API；真实 CLS 结论仍要求官方 MCP、凭据和用户目标可用。

当前还提供 Qwen/百炼模型 provider：本地 JSON typed settings、延迟创建的 ChatOpenAI/OpenAIEmbeddings、独立 qwen3-vl-rerank HTTP adapter、embedding 十条分批和 readiness 脱敏。Chat Agent、RAG 与知识索引已消费这些边界；自动化测试只使用 fake transport，不能代表真实百炼连通。

tenant isolation foundation 把当前 user id 显式映射为 tenant/owner scope，提供 owner-scoped Repository 治理和 SQLite 同语句 scope helper。`super_ai.vector_store` 提供 typed 本地 JSON 配置、延迟 PyMilvus client、1024/HNSW collection、insert/search/delete/health；retrieval Tool 捕获 CurrentUser 且模型不能传入 owner/tenant，也不暴露独立搜索 HTTP API。

Milvus adapter 必须先显式 `connect()` 或 `initialize()`，模块 import 和空知识库 search 不连接网络。同步 PyMilvus 调用在线程中执行，当前不公开虚构的 `close()`。真实服务 smoke 状态和命令见 `docs/runbooks/local-infrastructure.md`。

真实 Qwen+Milvus 联合 smoke 的前置条件和步骤见 `docs/runbooks/durable-document-indexing-smoke.md`；没有真实凭据或服务时不得声称已通过。

混合检索真实 smoke 的命令与未执行说明见 `docs/runbooks/reranked-hybrid-knowledge-retrieval-smoke.md`。

```bash
uv sync
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest
```
