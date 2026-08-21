# P21 AIOps Diagnosis and Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 durable LangGraph 运行 owner-scoped、可恢复且证据优先的 AIOps 诊断，并规范化保存过程、报告和 provenance。

**Architecture:** P09 background worker 惰性创建诊断 runtime，StateGraph 固定执行 Planner → Executor → Replanner → Report；节点完成时将领域记录、语义 job event 与项目自有 checkpoint 写入同一 SQLite 事务。所有外部结果经严格 normalizer 变成 evidence，报告模型只引用 evidence id，模型失败走不推导新事实的纯函数 fallback。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、LangGraph StateGraph、LangChain tools、Qwen ChatOpenAI、langchain-mcp-adapters、pytest/pytest-asyncio、Ruff、strict Pyright、TypeScript 5.6/Vitest。

**Spec:** `openspec/changes/run-aiops-diagnosis-and-store-evidence/design.md`

## Global Constraints

- 所有 Repository 方法以 `owner_user_id` 为首个业务参数；禁止先按 id 查询再补 owner 检查。
- 模块 import、FastAPI factory 和无任务启动不得连接 Qwen、Milvus 或 MCP。
- 生产路径不得生成 fake 日志、证据、分数、工具结果或根因；测试替身只能通过依赖注入进入。
- graph 最大 8 个计划步骤、最多 3 次重规划；最终计划恰好一个规范化名称为 `searchlog` 的真实工具步骤。
- stream 只使用既有八种 SSE type，job event sequence 是唯一序号权威。
- 外部调用不得持有 SQLite transaction；节点结果落库使用短事务。
- 全部 artifacts、主规格和归档使用简体中文；完成归档后只创建一个 P21 Conventional Commit。

---

### Task 1: Contracts 与诊断迁移

**Files:**
- Create: `packages/api-contracts/src/aiops.ts`
- Create: `packages/api-contracts/src/aiops.test.ts`
- Modify: `packages/api-contracts/src/sse.ts`
- Modify: `packages/api-contracts/contract-manifest.json`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Create: `apps/backend/migrations/versions/20260820_0011_add_aiops_diagnostics.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/diagnostic_models.py`
- Test: `apps/backend/tests/aiops/test_migration.py`

**Interfaces:**
- Produces: `DiagnosticTask`, `DiagnosticStep`, `DiagnosticEvidence`, `DiagnosticReport`, `ReportEvidenceLink`, `EvidenceChainData`, `DiagnosticCreateData`；六张 Alembic 表。
- Changes: `TaskLifecycle = queued|running|succeeded|failed|cancelled`；`TaskStatusData.progress?: number`。

- [ ] **Step 1: 写合同和迁移失败测试**

```python
async def test_fresh_upgrade_has_normalized_diagnostic_tables(tmp_database):
    await upgrade_database(tmp_database.url)
    names = await table_names(tmp_database.engine)
    assert {"diagnostic_tasks", "diagnostic_steps", "diagnostic_evidence",
            "diagnostic_reports", "report_evidence_links", "graph_checkpoints"} <= names
```

```typescript
it("诊断只复用共享 SSE 并对齐 durable 状态", () => {
  expect(TASK_LIFECYCLES).toEqual(["queued", "running", "succeeded", "failed", "cancelled"]);
  expect(SSE_EVENT_TYPES).not.toContain("plan");
  expect(SSE_EVENT_TYPES).not.toContain("replan");
});
```

- [ ] **Step 2: 运行定向测试并确认因类型/迁移缺失失败**

Run: `npm run test --workspace @super-ai/api-contracts -- src/aiops.test.ts && cd apps/backend && uv run pytest tests/aiops/test_migration.py -q`

- [ ] **Step 3: 实现最小合同、manifest、Pydantic、ORM 与迁移**

迁移明确建立 owner/task/step/evidence/report 外键和 `(owner_user_id, task_id)`、`(task_id, checkpoint_version)` 等索引；`report_evidence_links` 同时保存 owner/task，Repository 后续二次验证同域关联。

- [ ] **Step 4: 重跑 contracts 与 migration 测试至通过**

Run: `npm run contracts:typecheck && npm run contracts:test && cd apps/backend && uv run pytest tests/aiops/test_migration.py -q`

### Task 2: Owner-scoped Repository 与 durable event 扩展

**Files:**
- Create: `apps/backend/src/super_ai/aiops/models.py`
- Create: `apps/backend/src/super_ai/aiops/repositories.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/diagnostic_repositories.py`
- Modify: `apps/backend/src/super_ai/background_jobs/handlers.py`
- Modify: `apps/backend/src/super_ai/background_jobs/runtime.py`
- Modify: `apps/backend/src/super_ai/memory/extended_sqlite/background_job_repositories.py`
- Test: `apps/backend/tests/aiops/test_repositories.py`
- Test: `apps/backend/tests/background_jobs/test_runtime.py`

**Interfaces:**
- Produces: `DiagnosticRepository`, `DiagnosticStore`, `append_progress_event(owner_user_id, job_id, event_type, data)`。
- Changes: `BackgroundJobContext.termination_reason` 只读语义 `cancelled|timeout|shutdown|None`。

- [ ] **Step 1: 写两个用户、checkpoint、link 和 termination reason 失败测试**

```python
async def test_report_link_rejects_cross_owner_evidence(repository):
    report = await repository.create_report("user-a", task_id, draft)
    with pytest.raises(ValueError):
        await repository.link_evidence("user-a", task_id, report.id, user_b_evidence.id, claim)
```

```python
async def test_worker_exposes_timeout_without_marking_shutdown_as_cancelled(runtime_fixture):
    timeout_reason = await runtime_fixture.run_until_timeout()
    shutdown_reason = await runtime_fixture.stop_during_handler()
    assert timeout_reason == "timeout"
    assert shutdown_reason == "shutdown"
```

- [ ] **Step 2: 运行测试确认 owner/event 接口不存在而失败**

Run: `cd apps/backend && uv run pytest tests/aiops/test_repositories.py tests/background_jobs/test_runtime.py -q`

- [ ] **Step 3: 实现 records、Protocol、SQLite adapter 和最小 runtime 扩展**

外部工具调用前后不持有 Repository transaction；store 方法每次创建独立 transaction。semantic event 只保存 `eventType` 与安全 `data`，SSE base fields 留给 stream mapper。

- [ ] **Step 4: 重跑测试并执行 strict Pyright**

Run: `cd apps/backend && uv run pytest tests/aiops/test_repositories.py tests/background_jobs/test_runtime.py -q && uv run pyright`

### Task 3: Planner、SOP 与真实工具注册表

**Files:**
- Create: `apps/backend/src/super_ai/aiops/planning.py`
- Create: `apps/backend/src/super_ai/aiops/tools.py`
- Create: `apps/backend/src/super_ai/aiops/security.py`
- Test: `apps/backend/tests/aiops/test_planner.py`

**Interfaces:**
- Produces: `normalize_tool_name(name) -> str`、`PlanStep`、`PlanDraft`、`validate_plan(draft, registered_names)`、`DiagnosticPlanner.plan(context)`。
- Consumes: P12 `KnowledgeRetriever`、P18 `McpToolGateway`/owner target source、P15 audit service、可注入 structured model。

- [ ] **Step 1: 写顺序、no-SOP、SearchLog 唯一性和权限失败测试**

```python
async def test_planner_retrieves_sop_before_mcp_discovery(planner, calls):
    await planner.plan(context)
    assert calls[:2] == ["knowledge_retrieval:user-a", "mcp_discover:user-a"]

def test_plan_requires_exactly_one_registered_search_log():
    with pytest.raises(SearchLogUnavailableError):
        validate_plan(PlanDraft(steps=[tool_step("metric_query")]), {"metric_query"})
```

- [ ] **Step 2: 确认测试因 planner/validator 缺失而失败**

Run: `cd apps/backend && uv run pytest tests/aiops/test_planner.py -q`

- [ ] **Step 3: 最小实现固定装配顺序和两层 plan validation**

规范化只接受移除 `_`/`-`/空白后恰为 `searchlog`；模型修正最多一次，所有步骤必须命中本次 registry。

- [ ] **Step 4: 重跑 planner 测试至通过**

Run: `cd apps/backend && uv run pytest tests/aiops/test_planner.py -q`

### Task 4: Executor、Evidence normalizer 与 Replanner

**Files:**
- Create: `apps/backend/src/super_ai/aiops/evidence.py`
- Create: `apps/backend/src/super_ai/aiops/execution.py`
- Create: `apps/backend/src/super_ai/aiops/replanning.py`
- Test: `apps/backend/tests/aiops/test_execution.py`
- Test: `apps/backend/tests/aiops/test_replanning.py`

**Interfaces:**
- Produces: `EvidenceNormalizer.normalize(tool_name, output) -> tuple[NewEvidence, ...]`、`DiagnosticExecutor.execute_one(state)`、`ReplanDecision(action, plan, reason)`。
- Consumes: registered `BaseTool`、DiagnosticStore、AgentToolCallAuditStore、semantic event sink。

- [ ] **Step 1: 写真实结果、失败 audit、未知 payload 和 replan 上限测试**

```python
async def test_unknown_tool_payload_is_not_saved_as_evidence(executor, repository):
    with pytest.raises(EvidenceNormalizationError):
        await executor.execute_one(state_for_output(object()))
    assert await repository.list_evidence("user-a", task_id) == alert_evidence_only
```

```python
async def test_replanner_cannot_add_unregistered_tool(replanner):
    decision = await replanner.decide(state, model_plan=[tool_step("secret_tool")])
    assert decision.action == "failed"
```

- [ ] **Step 2: 运行测试确认失败原因是实现缺失**

Run: `cd apps/backend && uv run pytest tests/aiops/test_execution.py tests/aiops/test_replanning.py -q`

- [ ] **Step 3: 实现单步执行、有界 normalizer、审计和结构化重规划**

工具 output 仅在识别为 knowledge citation 或允许的 log/metric 结构时写 evidence；异常先脱敏再进入 step/audit/event。

- [ ] **Step 4: 重跑测试至通过**

Run: `cd apps/backend && uv run pytest tests/aiops/test_execution.py tests/aiops/test_replanning.py -q`

### Task 5: StateGraph、checkpoint 和报告

**Files:**
- Create: `apps/backend/src/super_ai/aiops/graph.py`
- Create: `apps/backend/src/super_ai/aiops/reporting.py`
- Create: `apps/backend/src/super_ai/aiops/fallback.py`
- Test: `apps/backend/tests/aiops/test_graph.py`
- Test: `apps/backend/tests/aiops/test_reporting.py`

**Interfaces:**
- Produces: `build_diagnostic_graph(runtime) -> CompiledStateGraph`、`DiagnosticGraphRunner.run(...)`、`validate_report_draft(...)`、`build_fallback_report(...)`。
- Consumes: Planner/Executor/Replanner、DiagnosticStore、structured report model。

- [ ] **Step 1: 写拓扑、恢复、固定标题、provenance 和 fallback 失败测试**

```python
def test_graph_has_required_edges(compiled_graph):
    edges = graph_edges(compiled_graph)
    assert required_edges <= edges
    assert ("report", "__end__") in edges

def test_fallback_never_invents_root_cause():
    report = build_fallback_report(alerts, steps=[], evidence=[])
    assert "证据不足，无法确定根因" in report.markdown
    assert report.links == ()
```

- [ ] **Step 2: 运行测试确认 graph/report 未实现而失败**

Run: `cd apps/backend && uv run pytest tests/aiops/test_graph.py tests/aiops/test_reporting.py -q`

- [ ] **Step 3: 实现 StateGraph、节点 checkpoint、报告校验与纯 fallback**

每个 report claim 的 evidenceIds 必须由 Repository 在同 owner/task 范围验证；无效模型结果直接使用 fallback，不尝试文本猜链接。

- [ ] **Step 4: 重跑 graph/report 测试至通过**

Run: `cd apps/backend && uv run pytest tests/aiops/test_graph.py tests/aiops/test_reporting.py -q`

### Task 6: Durable handler、API 与 SSE replay

**Files:**
- Create: `apps/backend/src/super_ai/aiops/handler.py`
- Create: `apps/backend/src/super_ai/aiops/dependencies.py`
- Create: `apps/backend/src/super_ai/aiops/service.py`
- Create: `apps/backend/src/super_ai/aiops/router.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Test: `apps/backend/tests/aiops/test_handler.py`
- Test: `apps/backend/tests/aiops/test_api.py`
- Test: `apps/backend/tests/aiops/test_stream.py`

**Interfaces:**
- Produces: lazy `create_aiops_diagnosis_handler_factory(...)`、`DiagnosticService`、五个 `/aiops/diagnostics` operations、job event→SSE mapper。
- Consumes: database runtime、LLM/vector/MCP settings、P09 HandlerRegistry、认证 CurrentUser。

- [ ] **Step 1: 写断线、restart/cancel/timeout、API owner 和 sequence replay 失败测试**

```python
async def test_stream_resume_does_not_duplicate_events(client, token):
    first = await collect_stream(client, task_id, token, after_sequence=0, limit=3)
    resumed = await collect_stream(client, task_id, token, after_sequence=first[-1].sequence)
    assert min(event.sequence for event in resumed) > first[-1].sequence
```

- [ ] **Step 2: 运行测试确认 handler/router 缺失而失败**

Run: `cd apps/backend && uv run pytest tests/aiops/test_handler.py tests/aiops/test_api.py tests/aiops/test_stream.py -q`

- [ ] **Step 3: 实现惰性 handler factory、服务、路由和持久轮询 stream**

stream generator 的 cancellation 只停止读取；只有通用 background-job cancel API 能改变 job。terminal event 映射后只发一个 complete，failed 先发共享 error 再 complete(error)。

- [ ] **Step 4: 重跑 API/stream 与 import-safety 测试**

Run: `cd apps/backend && uv run pytest tests/aiops tests/test_import_safety.py -q`

### Task 7: 治理、完整门禁、归档和单提交

**Files:**
- Modify: `tests/test_api_contract_governance.py`
- Modify: `apps/backend/tests/test_contract_manifest.py`
- Modify: `openspec/changes/run-aiops-diagnosis-and-store-evidence/tasks.md`
- Sync: `openspec/specs/aiops-diagnosis-and-evidence/spec.md`
- Sync: `openspec/specs/api-and-sse-contracts/spec.md`

**Interfaces:**
- Produces: 无 active P21 change、归档目录和一个 Conventional Commit。

- [ ] **Step 1: 增加禁止 private SSE、诊断专用 cancel/retry 和生产 fake evidence 的治理断言**

Run: `cd apps/backend && uv run pytest ../../tests/test_api_contract_governance.py tests/test_contract_manifest.py -q`

- [ ] **Step 2: 运行所有工程门禁**

```bash
cd apps/backend
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest
cd ../..
npm run contracts:typecheck
npm run contracts:test
openspec validate --all
git diff --check
```

- [ ] **Step 3: 执行 verify，修复所有 CRITICAL/WARNING 并重跑受影响门禁**

验证报告必须逐项映射 tasks、Requirements、Scenarios、StateGraph 拓扑、owner scope、无 fake 结论和报告 provenance。

- [ ] **Step 4: 同步 delta specs、归档 P21 并再次验证 OpenSpec**

归档目标：`openspec/changes/archive/2026-08-20-run-aiops-diagnosis-and-store-evidence/`。

- [ ] **Step 5: 创建用户要求的归档后 Git 提交**

```bash
git add apps/backend packages/api-contracts openspec docs tests
git diff --cached --check
git commit -m "feat: 完成 P21 AIOps 诊断与证据链"
git status --short
```
