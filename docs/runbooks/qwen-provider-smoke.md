# Qwen Provider 人工 Smoke

> 状态：**尚未执行**。本文件只记录有真实百炼凭据时的人工步骤；自动化 fake transport 测试通过不代表真实百炼连通性通过。

## 前置条件

1. 确认 `config/project.json` 和 `config/user.project.json` 均被 `git check-ignore` 命中。
2. 只在被忽略的 `config/user.project.json` 填写 `llm.apiKey`。
3. 如果百炼控制台提供 workspace 专属域名，同时覆盖 `llm.baseUrl` 与 `llm.rerank.endpoint`；不要把 key 写入模板、命令行参数或环境变量。
4. 确认账号已开通 qwen3.7-max、text-embedding-v4 与 qwen3-vl-rerank，接受最小请求可能产生费用。

## 执行

在 `apps/backend` 目录运行：

```bash
uv run python - <<'PY'
import asyncio
from pathlib import Path

from super_ai.llm import QwenOpenAIProvider, load_llm_settings


async def main() -> None:
    settings = load_llm_settings(
        Path("../../config/project.json"),
        Path("../../config/user.project.json"),
    )
    provider = QwenOpenAIProvider(settings)
    for capability in ("chat", "embedding", "rerank"):
        result = await provider.readiness(capability)
        print(result.model_dump(by_alias=True))


asyncio.run(main())
PY
```

## 人工验收

- 三类结果均只显示 provider、model、baseUrl 和非负 latency，不显示 API key 或 Authorization header。
- chat 模型为本机配置值；embedding 模型为 text-embedding-v4；rerank 模型为 qwen3-vl-rerank。
- 任一失败只记录已脱敏错误，不把失败改写为“通过”，也不生成 fallback 向量、排序或分数。
- 执行人应在独立运维记录中写明日期、区域/workspace 和结果；不要把真实 key 或完整响应提交到 Git。
