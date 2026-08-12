# Knowledge Documents and Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每个用户建立稳定默认知识库、owner-scoped Markdown/PDF 文档管理和预览/索引共用切分入口。

**Architecture:** knowledge 领域包含纯上传校验/提取、纯 splitter、冻结 record、Repository Protocol 和 service；ORM 仅位于 `super_ai.memory.extended_sqlite`。FastAPI multipart 路由消费共享 contracts，向量删除通过可注入 Protocol 复用 tenant-safe adapter。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、pypdf、langchain-text-splitters、pytest、TypeScript 5.6。

## Global Constraints

- 只允许 UTF-8 `.md`/`text/markdown` 与 `.pdf`/`application/pdf`，最大 `10 * 1024 * 1024` 字节。
- Repository 所有用户操作首个业务参数为 `owner_user_id`，父子查询同时约束 owner/KB/document。
- 默认 fixed-character 为 maxCharacters=1200、overlap=200，且 overlap < max。
- preview 最多 12 段，每段 excerpt 最多 400 字。
- 模块 import 不连接 SQLite/Milvus，不读取真实配置或密钥。

---

### Task 1: 合同与迁移

**Files:** `packages/api-contracts/src/knowledge.ts`、`contract-manifest.json`、`apps/backend/src/super_ai/api_contracts.py`、migration/models/tests。

**Interfaces:** 产出共享 DTO/policy 和 `knowledge_documents` schema，供 service/router 消费。

- [x] 先写合同与 migration 失败测试并运行确认因 P10 类型/表缺失失败。
- [x] 实现 DTO、manifest、ORM、revision `20260812_0004` 和 multipart 依赖。
- [x] 运行定向 contracts/migration 测试至通过。

### Task 2: 文件提取与切分

**Files:** `super_ai/knowledge/files.py`、`chunking.py`、`models.py` 及对应测试。

**Interfaces:** `validate_and_extract(filename, mime_type, content) -> ExtractedDocument`；`chunk_document_text(text, config) -> tuple[DocumentChunk, ...]`。

- [x] 先写 policy、PDF/Markdown 和三个 splitter 的失败测试。
- [x] 实现严格校验、pypdf 提取、config validation 与纯切分入口。
- [x] 验证 preview 12/400 限界与 metadata 可追溯。

### Task 3: Repository 与删除边界

**Files:** `knowledge/repositories.py`、`service.py`、`memory/extended_sqlite/knowledge_repositories.py`、测试。

**Interfaces:** 用户方法均显式 `owner_user_id`；`DocumentVectorDeleter.delete_document(scope, kb, document)`。

- [x] 先写默认 KB、跨 owner、重复/覆盖、软删除及 fake deleter 失败测试。
- [x] 实现 owner-scoped SQLite adapter 与 service 事务内状态改变。
- [x] 验证外部删除失败时 SQLite 文档保持活动。

### Task 4: API 与门禁

**Files:** `knowledge/router.py`、`dependencies.py`、`app.py`、API/contract/import 测试。

**Interfaces:** 六种操作使用 bearer、共享 envelope、multipart `file/chunkingConfig/overwrite`。

- [x] 先写端到端 API 失败测试。
- [x] 实现路由与依赖注入，验证 OpenAPI/manifest 对齐。
- [x] 运行 backend/contracts/OpenSpec/diff 全门禁、verify、sync 与 archive。
