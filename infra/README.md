# 基础设施边界

本目录当前只锁定未来边界，不提供 Compose 实现。

未来 Compose 只允许托管 etcd、MinIO、Milvus、Attu 和 Alertmanager。FastAPI 后端、Vue 前端和官方 CLS MCP Server 必须在主机运行，不得添加为 Compose 应用服务。

本项目不创建应用 `app.Dockerfile`、`project.compose.json` 或应用 Compose 服务。
