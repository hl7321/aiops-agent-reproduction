# Reranked Hybrid Knowledge Retrieval 人工 Smoke

## 当前状态

真实 Qwen embedding + Milvus + Qwen rerank smoke **未执行**。自动化门禁使用临时 SQLite、fake provider 和 fake vector store，不证明本机真实服务或凭据连通。

## 前置条件

1. `config/project.json` 与 `config/user.project.json` 已由模板复制且保持 Git ignored。
2. ignored 配置中的 Qwen API key、embedding/rerank endpoint 与 `vectorStore` 连接信息有效。
3. `infra/compose.yaml` 的 etcd、MinIO、Milvus 已健康，目标文档已通过 durable indexing 成功写入。
4. 不通过 OS 环境变量补充任何项目配置或凭据。

## 人工步骤

```bash
cd apps/backend
uv run alembic upgrade head
uv run pytest tests/retrieval -q
```

随后在显式加载 ignored JSON 的本地主机进程中创建 `QwenOpenAIProvider`、`MilvusVectorStore`、`KnowledgeRetrievalService` 与 owner-bound Tool，使用已成功索引文档中的中文、Java 类名和 trace/service token 分别查询。人工确认：

- 结果不超过 5 条且没有最低分阈值或兜底文本；
- citation 包含 vector/BM25/RRF/rerank 全阶段 rank/score；
- 其他用户 KB/document filter 返回空且不扩大 Milvus scope；
- provider 或 Milvus 失败时返回脱敏错误而不降级。

只有实际完成上述真实调用并保存时间、模型、服务版本和结果摘要后，才能把状态改为“已执行”。
