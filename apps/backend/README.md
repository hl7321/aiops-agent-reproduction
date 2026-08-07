# 后端工程基础

本 workspace 提供 FastAPI app factory、使用统一成功 envelope 的 `/health`、request ID 中间件、统一错误/验证/异常响应，以及通用 JSON 配置深合并。Pydantic 合同镜像由测试与 `packages/api-contracts/contract-manifest.json` 对齐。

新增 endpoint 前必须先扩展共享 OpenAPI path 和 HTTP 合同；endpoint 只能使用统一 response helper 和已登记错误 code。数据库、认证、聊天、Agent、LLM、Milvus 与 MCP 功能尚未实现。

```bash
uv sync
uv run ruff check .
uv run pyright
uv run pytest
```
