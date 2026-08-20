# Durable 文档索引真实 smoke

自动化测试只使用临时 SQLite、fake embedding 与 fake Milvus client，不代表真实 Qwen 或 Milvus 连通。

仅当以下条件全部满足时人工执行：

- 被 Git 忽略的 `config/user.project.json` 已填写有效 `llm.apiKey` 与 `vectorStore.token`；
- 本地 JSON 深合并结果能通过 P06/P07 typed validation；
- `docker compose -f infra/compose.yaml ps` 显示 Milvus、etcd、MinIO 可用；
- 后端已执行 `uv run alembic upgrade head` 并在主机启动。

人工步骤：注册/登录，上传一个会产生 10 段以上的 Markdown；显式调用文档的 `POST .../index-tasks`；轮询索引 task 详情与通用 background job，确认领域状态到 `succeeded`；在 Attu 中按 tenantId、knowledgeBaseId、documentId 检查全部 chunks、1024 维向量和 metadata。随后再次创建任务，确认旧向量被 scoped 替换而不是追加重复记录。

## 2026-08-17 执行结果

真实 Qwen+Milvus smoke **已通过**：桌面客户端分别上传 Markdown/PDF 并显式创建 durable index task，任务由 pending/running 到 `succeeded`；Markdown 手动重建再次成功。Milvus 抽查记录覆盖两个 documentId、3 个 chunk、1024 维向量、非空 tenant/KB/document scope，且 `tenantId == ownerUserId`。页面删除后强一致查询确认新建 Markdown/PDF documentId 均无残留；此前 wiring 缺口产生的 3 个精确 scope 也已清理，最终 `p13-smoke` 向量为 0。

本次未使用假向量、fake provider 或进程内临时任务，也未把 SQLite 与 Milvus 描述为跨系统原子事务。真实凭据仅存在于 ignored JSON，未进入日志或 Git。
