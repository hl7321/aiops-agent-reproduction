# 运行与监控

## 探针

- `/health`：只证明 FastAPI 进程存活，不读取或连接数据库、Milvus、Qwen、MCP。
- `/ready`：真实检查 SQLite、Milvus、Qwen Chat 和 CLS MCP；任一失败返回 503，并保留逐项 latency 与安全错误。
- `/config/check`：先检查两份本地 JSON 与 typed section，再执行同一依赖检查；配置无效和依赖不可达使用不同状态。
- `/health/mcp`：只检查真实 MCP discovery。
- `/metrics`：JSON envelope 内的本进程累计请求、失败和耗时；进程重启归零，不是 Prometheus exposition。

completion log 是单行 JSON，只含 requestId、path、status、duration。业务 lifecycle 只含 ID、状态、分类、耗时、工具名与参数键；禁止记录 header/body、query/prompt、参数值、工具输出、模型正文或凭据。

## 手动分步启动

```bash
docker compose -f infra/compose.yaml up -d
cd apps/backend && uv sync && uv run alembic upgrade head
uv run uvicorn super_ai.app:create_local_app --factory --host 127.0.0.1 --port 8000
npm run frontend:dev -- --host 127.0.0.1
```

官方 CLS MCP 在另一终端按官方文档以 Streamable HTTP 模式启动，配置 URL 为 `http://127.0.0.1:3000/mcp`。凭据只放 ignored JSON；不要放入 URL query。

停止应用进程不会删除 Compose volumes、SQLite、已下载镜像或 npm/uv 缓存。以后可重新运行启动脚本。`docker compose down` 停容器但保留命名卷；只有用户明确决定清数据时才考虑删除卷。

## 副作用边界

启动、探针和自动测试都不会上传日志、发布告警或 seed SOP。三类写入只能按教程显式执行；先确认自己的 CLS topic、Alertmanager URL 和测试账号。日志位于 `apps/backend/var`，该目录被 Git 忽略。
