# 后端工程基础

本 workspace 提供 FastAPI app factory、使用统一成功 envelope 的 `/health`、request ID 中间件、统一错误/验证/异常响应，以及通用 JSON 配置深合并。Pydantic 合同镜像由测试与 `packages/api-contracts/contract-manifest.json` 对齐。

持久化 foundation 已提供 SQLAlchemy 2 async runtime、Alembic migration、事务 scope、Repository Protocol、不可变 record 和 SQLite adapter 扩展边界。Alembic 是 schema 唯一权威；应用不会在导入或默认启动时连接数据库、自动迁移或调用 `metadata.create_all`。测试只使用 pytest 临时 SQLite 文件。

当前已实现本地认证、owner-scoped 文档管理、durable 文档索引和供后续 Agent 组装的 `knowledge_retrieval` Tool。上传只保存文档；客户端必须显式创建索引任务，后台 worker 才会复用保存的 splitter 配置、Qwen embedding 与 tenant-safe Milvus adapter。Tool 使用当前用户成功索引的文档执行 BM25L + Milvus 并行召回、RRF 与真实 Qwen rerank；完整 RAG、知识页面、聊天、MCP 与 AIOps 尚未实现。

当前还提供 Qwen/百炼模型 provider 基础：本地 JSON typed settings、延迟创建的 ChatOpenAI/OpenAIEmbeddings、独立 qwen3-vl-rerank HTTP adapter、embedding 十条分批和 readiness 脱敏。它不代表 Agent、聊天、RAG、知识库或真实百炼连通性已经实现；自动化测试只使用 fake transport，人工 smoke 尚未执行，步骤见 `docs/runbooks/qwen-provider-smoke.md`。

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
