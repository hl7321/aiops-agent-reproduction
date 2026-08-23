# P28 Schema-aware AIOps、可信证据与案例治理实施计划

> 实施以 `openspec/changes/harden-schema-aware-aiops-evidence-and-case-governance/` 为权威；每个行为先写失败测试，再写最小实现。

**目标：** AIOps 只调用 owner 本轮真实发现且经只读取证 policy 允许的 MCP 工具；对输入、输出和跨步参数确定性校验；按错误类别有界恢复；只有真实证据充分且经用户正向认可的报告才能显式沉淀为去重后的知识案例。

**架构：** 动态 MCP registry 与静态 `AiopsToolPolicy` 取交集形成 request-scoped capability catalog。Planner 只看到安全的名称、描述、Schema 摘要和条件依赖；Executor 调用前验证 runtime Schema 与本地 adapter，调用后把 MCP wrapper 解包为 typed artifact/evidence。Pydantic 只报告结构错误，classifier 决定 corrective retry、Replanner 或永久失败。claim evidence evaluator 产生报告 trust state；知识提升以 positive feedback、显式 API、canonical fingerprint 和 source provenance 约束写入。

## 不可变约束

- `Region`、`TopicId` 继续来自 ignored 本地 JSON；模型和客户端不能覆盖。
- SearchLog 是当前 CLS profile 必需能力；TextToSearchLogQuery 仅在 query 未经服务端验证时需要；DescribeLogContext 仅在时序 claim 且命中具备定位字段时需要。
- 未登记、有副作用、跨 owner、Schema 不兼容的工具一律不进入 Planner。
- 每个 step 最多 3 次 attempt；配置、权限、越权、未允许、永久 4xx、Schema 不兼容不重试。
- raw MCP JSON、完整参数值、日志正文、query、prompt、凭据不进入日志或 SSE。
- report 节点永不自动创建 case/document/index task。
- 只有 `verified_evidence`、`uncertainty=false`、完整 provenance、最新正向 report feedback 的报告可显式提升。

## 1. 合同与数据库

先修改 `packages/api-contracts/src/aiops.test.ts`、`src/index.test.ts`、backend contract/migration/case repository tests，断言 `DiagnosticStep.errorCategory`、`DiagnosticReport.trustState`、promotion result/candidate DTO、受保护 promotion path、report/step 新列、case fingerprint、`diagnostic_case_sources` 及 owner 唯一约束，并运行测试确认 RED。

然后修改 `packages/api-contracts/src/aiops.ts`、`contract-manifest.json`、`apps/backend/src/super_ai/api_contracts.py`、AIOps/case immutable records 与 owner-first repositories；新增 `apps/backend/alembic/versions/20260823_0014_harden_aiops_evidence_governance.py`。旧 report 默认不可提升，旧 case 不自动回填或重写向量。

验证：

```bash
npm run contracts:typecheck && npm run contracts:test
cd apps/backend
uv run pytest tests/aiops/test_contracts_and_planning.py tests/memory/test_migrations.py tests/aiops_cases -q
```

## 2. 双层白名单与 Planner 条件图

先在 `tests/aiops/test_tool_policy.py` 和 `test_contracts_and_planning.py` 测试动态发现与 policy 交集、未知/写工具拒绝、恢复时工具消失、可信 CQL 直接 SearchLog、自然语言先 builder、时序 claim 条件 context、非时序 claim 不强制 context、恰好一个 SearchLog。

新增 `super_ai/aiops/tool_policy.py`，实现 `AiopsToolPolicyEntry` 和安全 `ToolCapabilityDescriptor`；descriptor 只含名称、描述、Schema 摘要、依赖、证据类型、retry policy。更新 `planning.py`/`runtime.py`。Planner 校验失败最多纠正三次，只返回字段路径、错误类型和允许 Schema，不回传参数值。

## 3. Typed 工具 adapter

先新增 `tests/aiops/test_cls_tool_adapters.py`，以官方 Schema 和脱敏真实 wrapper 样本覆盖 `TextToSearchLogQuery`、`SearchLog`、`DescribeLogContext`，以及 QueryMetric 等其他允许工具的独立合同；非法 wrapper、缺字段、空 PkgId、错误 PkgLogId 必须失败。

新增 `tool_adapters.py` 与 `cls_tool_adapters.py`：统一解包 MCP content/structuredContent/artifact；核心三工具使用显式 Pydantic input/output model；所有允许工具先过 runtime input Schema。SearchLog/Context 的 Region、TopicId 强制使用配置；context 的 Time/PkgId/PkgLogId 只来自本轮 validated hit。修改 `evidence.py` 以 adapter 声明的 kind 持久化 query artifact、log hit、log context、metric、knowledge，删除工具名字符串推断。

## 4. 错误恢复与可信报告

先新增 `test_tool_recovery.py` 并扩展 runtime/repository tests，覆盖输入可修正、空结果 replan、timeout/429/5xx 退避、401/403/配置/越权/Schema 不兼容永久失败、三次上限、checkpoint/restart 与审计脱敏。

新增 `tool_failures.py` 与 `evidence_policy.py`。classifier 只输出 `retry_same_step | replan | permanent_failure`：retry 创建新 attempt；replan 只允许选择 catalog 中其他能力或修改非权威 query；permanent 立即终止必需能力。每次 attempt 独立写 step、audit、event、checkpoint，重启跳过已成功 attempt。

claim evaluator 明确 SearchLog 必需条件和时序 context 条件；工具数量不能决定可信。报告 trust state 仅为 `verified_evidence | insufficient_evidence | execution_failed`。LLM 失败说明始终不可提升；必需 runtime 失败不能被 fallback 改成 succeeded。删除 runtime report 节点的 `DiagnosisCasePersistor.persist` 调用。

## 5. 显式提升与 canonical 去重

先扩展 `tests/aiops_cases/`，覆盖无反馈、negative、删除反馈、uncertainty、非 verified、缺 provenance、跨 owner 均拒绝且零副作用；同 report 并发幂等、跨 task exact duplicate、semantic similar 待决策。

新增 `cases/fingerprints.py`，并修改 case service/router/repository 与 feedback owner-scoped 查询。promotion 在事务内重读 report、task、links和最新 feedback，忽略客户端 owner/approval。fingerprint v1 对规范化业务字段计算 SHA-256，排除随机 ID 和时间戳。exact duplicate 只追加 source；semantic similar 返回 `needs_review` 且不写文档/向量；明确 merge 只追加 provenance，明确 create-new 才建新 canonical case。legacy save-to-knowledge 也必须通过可信/反馈门禁。

## 6. Fixture 与前端

先扩展脚本测试，要求 Java 十个 incident 各有多行、单调时间、稳定且隔离的 context flow；保持 quant profile/count 兼容和 import 无副作用。修改 `scripts/java_ecommerce_aiops_fixtures.py` 与既有 `generate_and_upload_cls_logs.py`。

先扩展 frontend aiops client/store/component tests，覆盖 attempt/error category、trust state、正向 feedback 后 promotion、exact existing、semantic candidates、失败输入保留。随后修改 `aiopsClient.ts`、Pinia store、timeline/report/case UI。前端只显示安全分类、次数、摘要和门禁原因，不显示 raw JSON、权威配置或参数值。

## 7. 完整验证、归档和保存

```bash
cd apps/backend
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest
cd ../..
npm run contracts:typecheck
npm run contracts:test
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
python -m py_compile scripts/generate_and_upload_cls_logs.py scripts/java_ecommerce_aiops_fixtures.py
docker compose -f infra/compose.yaml config
openspec validate --all
uv run --project apps/backend python scripts/sync_wiki.py active
uv run --project apps/backend python scripts/sync_wiki.py audit-includes
uv run --project apps/backend python scripts/sync_wiki.py audit-counts
npm run docs:build
git diff --check
```

随后用 `$openspec-verify-change` 核对实现；修复 CRITICAL/WARNING 并重跑门禁。真实 Qwen/CLS/Milvus smoke 仅在用户确认且环境可用时执行，不用 fake 结果替代。最终同步 delta specs、归档 P28、运行 wiki archive/audit/docs build，再用 Conventional Commit 提交。
