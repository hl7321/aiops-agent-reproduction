## Context

见 `proposal.md`。P21 report 已规范化保存并在同一 durable handler 中将 task 转为 succeeded；P10 文档与 P11 index task 均通过 owner-scoped SQLite adapter 和同一请求/worker事务边界工作。当前知识文档没有独立 source metadata，需在 P22 迁移中补充有界 JSON metadata 并由索引 handler 合并进 chunk metadata。

## Goals / Non-Goals

**Goals:**
- 成功 report 之后自动、并发幂等地生成 case/document/index task。
- 手动保存保持独立且只复用底层文档/索引边界。
- case、文档 metadata 与向量 citation 保持 owner/source provenance。

**Non-Goals:**
- 不直接写 Milvus，不实现 case 编辑/删除或前端 case 页面。
- 不从失败报告推断 case，不让手动路径补写 structured case。

## Decisions

### 1. 自动路径使用独立 `DiagnosisCasePersistor`

Persistor 接收 session factory，在一个短事务中重新 owner-scoped 读取 task/report/evidence，验证 task=succeeded 和 report 是该 task 的最终报告，然后通过 P10 `KnowledgeDocumentService.upload` 与 P11 `DocumentIndexTaskService.create` 创建文档、领域 index task 与 background job，最后写 case。它不持有 LLM/Milvus client。备选方案是在 P21 runtime 内直接写四张表，会绕过文档冲突、默认 KB 与 durable indexing 规则，因此拒绝。

### 2. `task_id` 唯一是自动幂等权威

自动入口先按 owner/task 查询；数据库对 case.task_id 建全局唯一约束。并发冲突回滚后重新 owner-scoped 读取赢家记录，绝不创建第二套资产。文档内容由 source task/report 与结构化字段确定，活动 hash 唯一约束作为第二道防线。legacy 手动入口使用独立 `LegacyDiagnosisKnowledgeSaver`，重复 hash 按现有 BUSINESS_CONFLICT 返回，不查询或创建 case。

### 3. report 成功顺序为 report/links → succeeded → case → SSE success

P21 report 节点先保存 report/links，再将 task 转为 succeeded，使 Persistor 的前置条件可验证；随后调用 Persistor。Persistor 失败会使 handler 顶层把 task 转为 failed，background job 依现有 retry 规则恢复，且不会发成功 report/complete 终态。retry 再次执行时依靠 task 唯一约束返回既有 case。

### 4. Markdown 与 source metadata 使用确定性纯函数

结构提取不再次调用模型：从最终 Markdown 固定章节和真实 alert/evidence 摘取有界 alertName/service/keywords/rootCause/remediation/summary。无法提取时保留诚实空字符串或“证据不足”，不编造。Markdown 使用 YAML-like frontmatter 与固定中文段落，source metadata 同时落 `knowledge_documents.source_metadata`，索引 handler 将其合并到每个 chunk metadata。

### 5. API 与 Repository owner-first

case Repository Protocol 的所有方法以 owner_user_id 为首个业务参数；列表/详情只查询 owner scope。手动保存先 owner-scoped 验证 succeeded task 和 final report，再创建资产。直接 case/task 不存在或跨 owner 使用 BUSINESS_RESOURCE_NOT_FOUND。

## Risks / Trade-offs

- [SQLite 并发在文档 hash 或 task 唯一约束处竞争] → 事务回滚后只对自动路径重读 winner，手动路径保持冲突。
- [report 文本提取不完美] → 使用有界确定性规则并保留完整 report/document provenance，不二次生成结论。
- [case 创建成功但后续向量索引失败] → case 保留 pending/failed index task 关联，由 P11 retry 恢复，不宣称跨 SQLite/Milvus 原子事务。

## Migration Plan

1. Alembic 0012 增加文档 source metadata 与 case 表，downgrade 先删 case 再删 metadata 列。
2. contracts/Repository/纯函数测试先失败，再实现 service、runtime hook 与 API。
3. 运行完整迁移、后端/contracts/OpenSpec 门禁；真实链路环境不完整时明确不执行 smoke。
