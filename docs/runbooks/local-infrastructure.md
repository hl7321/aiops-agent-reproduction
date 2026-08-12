# 本地基础设施与 Milvus smoke

> 真实 Milvus smoke 状态：**尚未执行**。2026-08-10 检查时 `127.0.0.1:19530` 端口可达，但 ignored 本地 JSON 中 `vectorStore.token` 仍为空；未绕过 typed 配置边界执行连接或初始化。自动化 fake client 测试通过不代表真实服务认证、schema 或检索通过。

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
