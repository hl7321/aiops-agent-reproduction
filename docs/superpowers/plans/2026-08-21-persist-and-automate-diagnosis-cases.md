# Persist and Automate Diagnosis Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将成功诊断自动、幂等地沉淀为结构化 case、知识文档和 durable index task，并保留独立 legacy 手动保存路径。

**Architecture:** 新增 owner-first case Repository 与独立自动 Persistor；Persistor 在 P21 report 成功节点中使用同一 SQLite 事务组合 P10/P11 边界。知识文档增加有界 source metadata，索引时合并到 chunk metadata；手动 saver 独立且不写 case。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy 2 async、aiosqlite、Alembic、pytest/pytest-asyncio、TypeScript contracts、Vitest。

**Spec:** `openspec/changes/persist-and-automate-diagnosis-cases/design.md`

## Global Constraints

- 所有 Repository 操作 owner_user_id 第一；跨 owner 不可枚举。
- Alembic 是 schema 唯一权威；import/startup 不创建外部 client 或知识资产。
- 自动路径不得直写 Milvus；手动路径不得创建 structured case。
- 先写失败测试、观察预期失败，再写最小实现并运行相关门禁。

---

### Task 1: Contracts 与 Alembic schema

**Files:** contracts aiops/openapi/manifest、`api_contracts.py`、0012 migration、case models/tests。

**Interfaces:** Produces `DiagnosticCase`, `DiagnosisCaseRepository`, `source_metadata` document field.

- [ ] 写 contracts/migration 失败测试并确认失败。
- [ ] 实现 DTO、operations、migration/models。
- [ ] 运行 contracts、migration、Ruff、Pyright targeted gates。

### Task 2: Repository 与确定性内容生成

**Files:** `aiops/cases/{models,repositories,content}.py`、SQLite adapter、case tests。

**Interfaces:** Produces owner-first CRUD and `build_diagnosis_case_material(...)`.

- [ ] 写 owner/唯一/回滚/Markdown/空 evidence 失败测试。
- [ ] 实现最小 record、adapter 与纯函数。
- [ ] 运行 targeted tests。

### Task 3: 文档 metadata 与索引传播

**Files:** knowledge models/repositories/service、document indexing handler/tests。

**Interfaces:** `KnowledgeDocumentRecord.source_metadata`; upload accepts optional source metadata.

- [ ] 写 metadata 持久化和 chunk merge 失败测试。
- [ ] 实现 metadata 全链路，保持默认上传兼容。
- [ ] 运行 knowledge/document-index tests。

### Task 4: 自动 Persistor 与 runtime hook

**Files:** `aiops/cases/persistor.py`、P21 runtime/factory、tests。

**Interfaces:** `persist(owner_user_id, task_id, report_id) -> DiagnosticCaseRecord`.

- [ ] 写前置条件、幂等、并发与 runtime 顺序失败测试。
- [ ] 实现短事务组合与唯一冲突恢复。
- [ ] 注入 production runtime 并运行 targeted tests。

### Task 5: Legacy saver 与 APIs

**Files:** case service/dependencies/router、contracts/API tests。

**Interfaces:** list/get case；save-to-knowledge 返回 document/indexTask。

- [ ] 写 API/owner/hash conflict/不写 case 失败测试。
- [ ] 实现独立 saver 与三条 operation。
- [ ] 运行 API/contract tests。

### Task 6: 闭环、治理与完整门禁

**Files:** retrieval integration/governance tests、OpenSpec tasks/specs。

- [ ] 测试索引→下一轮检索和跨 owner。
- [ ] 运行完整 backend/contracts/OpenSpec/diff gates。
- [ ] verify、修复、同步、归档、Conventional Commit。
