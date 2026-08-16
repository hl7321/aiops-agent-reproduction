# Reranked Hybrid Knowledge Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Agent 提供 tenant-safe 的 `knowledge_retrieval` LangChain Tool，执行 BM25L 与 Milvus 并行召回、RRF(k=60) 融合和真实 Qwen rerank，并返回完整阶段证据。

**Architecture:** `super_ai.retrieval` 分为合同模型、tokenizer/BM25L、RRF、service 和 Tool factory；SQLite Repository 只读取当前 owner 活动且索引成功的文档，P10 splitter 与共享稳定 chunkId 生成 BM25 语料。Service 把完整向量分支和 BM25 分支放入同一个 `asyncio.gather`，融合后最多 rerank 20 条并返回最多 5 条 citation。

**Tech Stack:** Python 3.10、Pydantic v2、SQLAlchemy 2 async、rank-bm25 BM25L、LangChain 1.x StructuredTool、pymilvus 3、pytest/pytest-asyncio、Ruff、strict Pyright、TypeScript 5.6/Vitest。

## Global Constraints

- 只允许 `from super_ai...`，模块 import 不得读取真实配置、创建外部 client 或连接网络。
- Tool 输入不得出现 owner/tenant；ownerUserId 与 tenantId 永远来自 CurrentUser，二者在当前模型中相等。
- Milvus filter 只包含 tenantId + allowedKnowledgeBaseIds；documentIds 在 owner-scoped 粗召回后过滤。
- 必须使用 BM25L，不得使用 BM25Okapi、仅向量 fallback、假分数或最低 rerank 阈值。
- query 非空，topK 默认 5 且范围 1..5；RRF k=60，rerank 候选最多 20。
- OpenSpec artifacts 和 README 使用简体中文，不增加独立搜索 HTTP endpoint。

---

### Task 1: Shared Tool Contracts

**Files:**
- Create: `packages/api-contracts/src/knowledge-retrieval.ts`
- Modify: `packages/api-contracts/src/index.ts`
- Modify: `packages/api-contracts/src/index.test.ts`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Modify: `apps/backend/tests/test_api_contracts.py`

**Interfaces:**
- Produces: `KnowledgeRetrievalToolInput`, `KnowledgeRetrievalCitation`, `KnowledgeRetrievalToolOutput` in TypeScript and Pydantic.
- Input fields: `query`, `topK=5`, `knowledgeBaseIds?`, `documentIds?`; no owner/tenant.
- Citation fields: stable ids/content/metadata and nullable vector/BM25 rank-score plus required RRF/rerank/score.

- [ ] Write contract tests that import the three types, assert nullable fields and ensure OPENAPI_PATHS is unchanged.
- [ ] Run `npm run contracts:test` and backend contract tests; confirm missing exports/models fail.
- [ ] Add the minimal TypeScript/Pydantic models with strict topK/query validation and alias serialization.
- [ ] Re-run contract typecheck/tests and mark OpenSpec tasks 1.1-1.2 complete.

### Task 2: Tokenizer, BM25L and RRF Pure Functions

**Files:**
- Create: `apps/backend/src/super_ai/retrieval/tokenizer.py`
- Create: `apps/backend/src/super_ai/retrieval/bm25.py`
- Create: `apps/backend/src/super_ai/retrieval/fusion.py`
- Create: `apps/backend/src/super_ai/retrieval/models.py`
- Test: `apps/backend/tests/retrieval/test_tokenizer_bm25.py`
- Test: `apps/backend/tests/retrieval/test_fusion.py`

**Interfaces:**
- Produces: `tokenize_for_retrieval(text: str) -> tuple[str, ...]`.
- Produces: `score_bm25l(query, corpus) -> tuple[RankedCandidate, ...]` using `rank_bm25.BM25L` only.
- Produces: `reciprocal_rank_fusion(vector_hits, bm25_hits, *, limit=20, rrf_k=60)`.

- [ ] Write tokenizer/BM25L tests for Chinese unigram+bigram, casefolded ASCII tokens, positive small-corpus match and zero disjoint score.
- [ ] Run targeted tests and confirm module-not-found RED.
- [ ] Implement Unicode normalization/tokenization and BM25L finite/nonnegative scoring; re-run GREEN.
- [ ] Write RRF tests for `1/61+1/62`, nullable branch evidence, chunkId tie and 20 limit; confirm RED.
- [ ] Implement immutable candidate records and deterministic fusion; re-run GREEN and mark tasks 1.3-1.5 complete.

### Task 3: Stable Chunk Identity and Owner Corpus Repository

**Files:**
- Create: `apps/backend/src/super_ai/knowledge/chunk_identity.py`
- Modify: `apps/backend/src/super_ai/document_indexing/handler.py`
- Modify: `apps/backend/src/super_ai/memory/extended_sqlite/knowledge_repositories.py`
- Test: `apps/backend/tests/retrieval/test_corpus_repository.py`
- Modify: `apps/backend/tests/document_indexing/test_handler.py`

**Interfaces:**
- Produces: `stable_chunk_id(document_id: str, index: int, content: str) -> str` shared by indexing/retrieval.
- Produces: `SqliteKnowledgeDocumentRepository.list_retrieval_corpus(owner_user_id, knowledge_base_ids, document_ids=None)` returning succeeded active immutable records.

- [ ] Write regression/repository tests proving identical chunk ids, succeeded-only records, owner+KB+document SQL scope and cross-owner emptiness; confirm RED.
- [ ] Extract stable chunk identity and replace P11 private helper.
- [ ] Implement the owner-first corpus query with deterministic ordering; run targeted tests GREEN and mark tasks 2.1-2.2 complete.

### Task 4: Hybrid Retrieval Service

**Files:**
- Create: `apps/backend/src/super_ai/retrieval/service.py`
- Create: `apps/backend/src/super_ai/retrieval/errors.py`
- Create: `apps/backend/tests/retrieval/fakes.py`
- Test: `apps/backend/tests/retrieval/test_service.py`

**Interfaces:**
- Consumes: `LlmProvider.embed_documents/rerank`, Milvus `initialize/search`, owner-scoped corpus loader.
- Produces: `KnowledgeRetrievalService.retrieve(current_user, input) -> KnowledgeRetrievalToolOutput`.
- Vector branch uses `VectorScope(owner, owner, allowed_kbs)`, limit 20 and post-filters document ids.

- [ ] Write input/default/authorization/empty-scope tests and confirm RED before implementation.
- [ ] Write an event-gated concurrency test proving both branches start before either completes.
- [ ] Write single-branch/RRF/rerank reorder/low-score/fewer-results/empty-results tests with full citation assertions.
- [ ] Write parameterized embedding/vector/BM25/rerank failures containing sentinel secrets and assert safe stage errors with no partial success.
- [ ] Implement the minimal service, strict vector/rerank shape validation, gather cleanup, RRF and citation mapping.
- [ ] Run targeted retrieval tests GREEN and mark tasks 2.3-2.7 complete.

### Task 5: LangChain Tool and Governance

**Files:**
- Create: `apps/backend/src/super_ai/retrieval/tool.py`
- Create: `apps/backend/src/super_ai/retrieval/__init__.py`
- Test: `apps/backend/tests/retrieval/test_tool.py`
- Modify: `apps/backend/tests/test_import_safety.py`
- Modify: `test_repository_policy.py`
- Modify: `apps/backend/README.md`
- Create: `docs/runbooks/reranked-hybrid-knowledge-retrieval-smoke.md`

**Interfaces:**
- Produces: `create_knowledge_retrieval_tool(current_user: CurrentUser, service: KnowledgeRetrievalService) -> StructuredTool` named `knowledge_retrieval`.
- Tool coroutine validates the Pydantic input and captures current user in its closure.

- [ ] Write Tool schema/name/owner capture tests and confirm RED.
- [ ] Implement StructuredTool factory with async coroutine only and safe ToolException mapping.
- [ ] Add source/import governance tests blocking BM25Okapi, create_task, private contract copies, ownerless Repository access and HTTP search paths.
- [ ] Update README/runbook without claiming real smoke; run targeted tests and mark tasks 3.1-3.4 complete.

### Task 6: Full Verification, OpenSpec Verify and Archive

**Files:**
- Modify: `openspec/changes/provide-reranked-hybrid-knowledge-retrieval/tasks.md`
- Create after sync: `openspec/specs/reranked-hybrid-knowledge-retrieval/spec.md`
- Modify after sync: `openspec/specs/api-and-sse-contracts/spec.md`

- [ ] Run `uv run ruff check .`, `uv run pyright`, `uv run pytest` and schema/migration regression.
- [ ] Run contracts typecheck/test and frontend typecheck/test/build.
- [ ] Run `openspec validate --all` and `git diff --check`.
- [ ] Execute `$openspec-verify-change`; map every requirement/scenario to code/tests and fix every CRITICAL/WARNING.
- [ ] Fetch archive/spec instructions, intelligently sync both delta specs, validate all specs, archive to the dated directory, and confirm `openspec list --json` is empty.
