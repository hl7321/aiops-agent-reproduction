## 1. 合同与迁移

- [x] 1.1 先增加 contracts 失败测试，定义 DiagnosticCase、case list/detail、legacy save data 与三个受保护 operations，并同步 TypeScript、Pydantic、manifest/OpenAPI。
- [x] 1.2 先增加 fresh migration/metadata 失败测试，再用 Alembic 0012 创建 `aiops_diagnostic_cases` 及 `knowledge_documents.source_metadata`。
- [x] 1.3 定义不可变 case record 与 owner-first Repository Protocol；测试唯一 task、排序、详情、跨 owner 和事务回滚后实现 SQLite adapter。

## 2. 确定性 case 内容与知识 metadata

- [x] 2.1 先测试多告警、空证据、证据不足、有界字段和 Markdown provenance，再实现 report/evidence 的确定性结构提取与文档生成纯函数。
- [x] 2.2 扩展 KnowledgeDocument record/repository/service 支持 source metadata，并测试索引 handler 把 metadata 合并进每个 chunk，保留 tenant/owner 既有边界。

## 3. 自动主路径

- [x] 3.1 先测试 succeeded+report 前置条件、失败/取消/无 report 拒绝，再实现独立 `DiagnosisCasePersistor` 组合文档、index task、job 与 case。
- [x] 3.2 先测试串行重复和并发唯一，再实现 task_id 唯一冲突恢复，确保只产生一套 case/document/index 资产。
- [x] 3.3 将 Persistor 注入 P21 production runtime；report/links→succeeded→case→成功事件，测试失败不发成功 complete、retry 返回既有 case。

## 4. legacy 手动路径与查询 API

- [x] 4.1 先测试 legacy succeeded/owner/report/hash conflict，再实现独立 `LegacyDiagnosisKnowledgeSaver`，只创建 document/index task，不写 case。
- [x] 4.2 先测试列表/详情/envelope/requestId/跨 owner，再实现 GET case list/detail 与 POST save-to-knowledge 路由和依赖注入。

## 5. 检索闭环与治理

- [x] 5.1 用 fake embedding/Milvus 测试 case 文档经过 P11 索引后被下一轮 owner-scoped knowledge_retrieval 命中，并断言跨 owner 不命中。
- [x] 5.2 增加治理/import-safety 测试，禁止自动路径直写向量、手动路径写 case、启动时自动沉淀或在日志中泄露 report/evidence。

## 6. 验证与归档准备

- [x] 6.1 执行 Alembic upgrade、backend Ruff/Pyright/pytest、contracts typecheck/test，修复全部问题。
- [x] 6.2 执行 `openspec validate --all` 与 `git diff --check`；真实链路仅在 Qwen、Milvus、已索引输入和 CLS MCP 均可用时执行，否则如实记录未执行。
- [x] 6.3 使用 `$openspec-verify-change` 核对 tasks、requirements、scenarios 和 design，修复所有 CRITICAL/WARNING 后同步 specs、归档并 Git 提交。
