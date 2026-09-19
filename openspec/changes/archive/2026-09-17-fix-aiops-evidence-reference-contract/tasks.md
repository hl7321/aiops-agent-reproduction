## 1. 影响面核实

- [x] 1.1 全仓检索 `DiagnosticEvidenceKind` 与 `DIAGNOSTIC_EVIDENCE` 的引用点，确认当前只有 `packages/api-contracts/src/aiops.ts`（定义）与 `packages/api-contracts/src/sse.ts`（guard）两处，没有其他隐藏副本
- [x] 1.2 检索仓库内是否还存在其他手写的证据种类字符串数组（例如后端镜像或 manifest），记录结论；若存在，纳入本次收敛范围
- [x] 1.3 在真实失败现场确认过 `kind` 为 `query_artifact` 的事件已被后端发出（数据库 `background_job_events` 中可见），作为修复前后的对照证据

## 2. 契约改造

- [x] 2.1 在 `packages/api-contracts/src/aiops.ts` 导出 `DIAGNOSTIC_EVIDENCE_KINDS`（`as const` 只读数组，包含全部 7 种诊断证据种类）
- [x] 2.2 将 `DiagnosticEvidenceKind` 改为由 `DIAGNOSTIC_EVIDENCE_KINDS` 派生，删除原来的手写联合类型
- [x] 2.3 修改 `packages/api-contracts/src/sse.ts` 的 `isDiagnosticEvidenceReference`，改为引用 `DIAGNOSTIC_EVIDENCE_KINDS`，删除手写的 4 项数组
- [x] 2.4 处理类型收窄：`as const` 数组的 `includes` 参数会被收窄为字面量联合，按 design.md 决策 1 的缓解方案收窄入参，必要时补充导出精确类型
- [x] 2.5 运行 `npm run contracts:typecheck` 确认契约包类型通过
- [x] 2.6 在 `apps/backend/src/super_ai/api_contracts.py` 将 `ReferenceSourceData.source` 改为 `ReferenceSource | DiagnosticEvidenceReference`，由结构分流 chat 与 aiops 两种引用形状
- [x] 2.7 删除从未被引用的 `DiagnosticReferenceSourceData` 与 `DiagnosticReferenceSourceEvent`，消除同一事件的第二份描述

## 3. 测试补齐

- [x] 3.1 在 `packages/api-contracts/src/index.test.ts` 增加用例：遍历 `DIAGNOSTIC_EVIDENCE_KINDS`，为每个取值构造 `channel: "aiops"` 的 `reference.source` 事件，断言 `isSseEvent` 返回 true
- [x] 3.2 在同一文件增加反向用例：未知证据种类（例如 `"private_kind"`）必须被 `isSseEvent` 拒绝
- [x] 3.3 确认既有 chat 频道 `reference.source` 用例（含分数漂移拒绝）保持通过，不修改其断言
- [x] 3.4 在 `apps/backend/tests/test_contract_manifest.py` 增加用例：遍历后端 `EvidenceKind` 的每个取值，构造证据引用形状并断言与共享契约一致
- [x] 3.5 在 `apps/frontend/src/transport/sseClient.test.ts` 增加用例：逐种喂入 aiops 频道全部合法证据种类的 `reference.source` 帧，断言解析器产出事件而不抛错；同时断言未知种类仍然抛"不符合共享事件合同"

## 4. 门禁验证

- [x] 4.1 `npm --workspace packages/api-contracts run test`
- [x] 4.2 `npm run frontend:typecheck` 与 `npm run frontend:test`
- [x] 4.3 在 `apps/backend` 运行 `uv run pytest tests/test_contract_manifest.py tests/test_api_contracts.py -q`
- [x] 4.4 在 `apps/backend` 运行 `uv run ruff check .` 与 `uv run pyright`
- [x] 4.5 `openspec validate --all`
- [x] 4.6 `git diff --check`

## 5. 真实 smoke 与归档

- [x] 5.1 人工 smoke：在本地完整栈上重跑一次真实诊断，确认 SSE 不再断流、前端时间线完整显示到报告（不得用 mock 结果代替）
- [x] 5.2 核对实现与 design.md 的偏差；若有偏差，更新 design.md 使其与实现一致
- [x] 5.3 运行 `openspec verify` 核对任务与规格覆盖情况，确认无 CRITICAL 问题
- [x] 5.4 归档 change，并用仓库的 wiki-sync 流程同步 `docs/changes/`，确认 VitePress 可构建
