# Durable 文档索引真实 smoke

自动化测试只使用临时 SQLite、fake embedding 与 fake Milvus client，不代表真实 Qwen 或 Milvus 连通。

仅当以下条件全部满足时人工执行：

- 被 Git 忽略的 `config/user.project.json` 已填写有效 `llm.apiKey` 与 `vectorStore.token`；
- 本地 JSON 深合并结果能通过 P06/P07 typed validation；
- `docker compose -f infra/compose.yaml ps` 显示 Milvus、etcd、MinIO 可用；
- 后端已执行 `uv run alembic upgrade head` 并在主机启动。

人工步骤：注册/登录，上传一个会产生 10 段以上的 Markdown；显式调用文档的 `POST .../index-tasks`；轮询索引 task 详情与通用 background job，确认领域状态到 `succeeded`；在 Attu 中按 tenantId、knowledgeBaseId、documentId 检查全部 chunks、1024 维向量和 metadata。随后再次创建任务，确认旧向量被 scoped 替换而不是追加重复记录。

本 change 的自动化验收环境未使用真实凭据，也未启动或探测本机外部服务，因此真实 Qwen+Milvus smoke **未执行**，不声称真实连通性通过。
