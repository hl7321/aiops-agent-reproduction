# 本地基础设施边界

`compose.yaml` 是本项目五个基础镜像版本的唯一事实来源，只运行 etcd、MinIO、Milvus standalone、Attu 和 Alertmanager。FastAPI 后端、Vue 前端和官方 CLS MCP Server 必须在主机运行，不得添加为 Compose 应用服务。

MinIO 只为 Milvus standalone 提供内部对象存储，不是应用文档对象存储。本项目不在 Compose 中运行日志上传、SOP seed 或其他产品任务，也不创建应用 `app.Dockerfile`、`project.compose.json`、`env_file` 或应用 Compose 服务。

```bash
docker compose -f infra/compose.yaml config
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
docker compose -f infra/compose.yaml down
```

命名卷默认跨 `down` 保留。完整说明和人工 smoke 步骤见 `docs/runbooks/local-infrastructure.md`。
