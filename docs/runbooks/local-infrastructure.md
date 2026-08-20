# 本地基础设施与 Milvus smoke

> 真实 Milvus smoke 状态：**已于 2026-08-17 执行通过**。typed ignored JSON 配置完成 connect、initialize 与 health；服务端版本为 `3.0-beta`，collection 为 `super_ai_chunks`。凭据未输出、未提交。

## 静态验证与启动

```bash
docker compose -f infra/compose.yaml config
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
```

只有 etcd、MinIO、Milvus、Attu 和 Alertmanager 应出现。后端、前端、官方 CLS MCP Server 继续在主机运行。MinIO 只服务于 Milvus，不上传应用文档。

停止服务但保留命名卷：

```bash
docker compose -f infra/compose.yaml down
```

## 有效 ignored 配置下的人工 smoke

先只在被 Git 忽略的 `config/user.project.json` 中填写本地 Milvus token，保持项目模板凭据为空。确认 `config/project.json` 和 `config/user.project.json` 均未被追踪后，在仓库根执行：

```bash
git check-ignore config/project.json config/user.project.json
cd apps/backend
uv run python - <<'PY'
import asyncio
from pathlib import Path

from super_ai.vector_store import MilvusVectorStore, load_vector_store_settings


async def main() -> None:
    settings = load_vector_store_settings(
        Path("../../config/project.json"),
        Path("../../config/user.project.json"),
    )
    store = MilvusVectorStore(settings)
    await store.connect()
    await store.initialize()
    print(await store.health())


asyncio.run(main())
PY
```

只有命令真实成功时才能把本页状态改为“已通过”，并记录日期、Milvus 服务版本和使用的 collectionName；不得记录 token。失败时保留错误类型并确认输出不包含凭据。

2026-08-17 的 Compose 五服务均成功启动；Milvus、etcd、MinIO、Alertmanager 健康，Attu 随 Milvus 启动。P13 真实索引进一步验证了 1024 维 insert、scoped replace/delete 和强一致查询。
