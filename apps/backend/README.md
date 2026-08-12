# 后端工程基础

本 workspace 提供 FastAPI app factory、使用统一成功 envelope 的 `/health`、request ID 中间件、统一错误/验证/异常响应，以及通用 JSON 配置深合并。Pydantic 合同镜像由测试与 `packages/api-contracts/contract-manifest.json` 对齐。

持久化 foundation 已提供 SQLAlchemy 2 async runtime、Alembic migration、事务 scope、Repository Protocol、不可变 record 和 SQLite adapter 扩展边界。Alembic 是 schema 唯一权威；应用不会在导入或默认启动时连接数据库、自动迁移或调用 `metadata.create_all`。测试只使用 pytest 临时 SQLite 文件。

当前已实现本地用户注册、登录、登出和 `/auth/me`：密码使用 Argon2 hash，opaque bearer token 在 SQLite 中只保存 SHA-256 hash，session 仅支持显式撤销，尚无自动过期策略。新增 endpoint 前必须先扩展共享 OpenAPI path 和 HTTP 合同；endpoint 只能使用统一 response helper 和已登记错误 code。聊天、知识、任务、MCP、AIOps、反馈、审计、Agent、LLM 与 Milvus 的领域功能尚未实现。

当前还提供 Qwen/百炼模型 provider 基础：本地 JSON typed settings、延迟创建的 ChatOpenAI/OpenAIEmbeddings、独立 qwen3-vl-rerank HTTP adapter、embedding 十条分批和 readiness 脱敏。它不代表 Agent、聊天、RAG、知识库或真实百炼连通性已经实现；自动化测试只使用 fake transport，人工 smoke 尚未执行，步骤见 `docs/runbooks/qwen-provider-smoke.md`。

tenant isolation foundation 把当前 user id 显式映射为 tenant/owner scope，提供 owner-scoped Repository 治理和 SQLite 同语句 scope helper。`super_ai.vector_store` 在此基础上提供 typed 本地 JSON 配置、延迟 PyMilvus client、1024/HNSW collection、insert/search/delete/health 和 fake client 测试；它仍不包含知识库资源表、文档解析、embedding pipeline、retrieval tool 或产品 RAG。

Milvus adapter 必须先显式 `connect()` 或 `initialize()`，模块 import 和空知识库 search 不连接网络。同步 PyMilvus 调用在线程中执行，当前不公开虚构的 `close()`。真实服务 smoke 状态和命令见 `docs/runbooks/local-infrastructure.md`。

```bash
uv sync
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest
```
