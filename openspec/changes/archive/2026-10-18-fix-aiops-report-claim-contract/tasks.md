# Tasks

## 1. 共享契约与错误目录

- [x] 1.1 在 TypeScript 错误目录中新增 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`（system / 200 / 安全默认消息），并在 `packages/api-contracts/src/aiops.test.ts` 与 `index.test.ts` 断言其存在与取值；运行 `npm --workspace packages/api-contracts run test` 通过
- [x] 1.2 在后端 `ErrorCode` 字面量与 `ERROR_DEFINITIONS` 中登记同一错误码，并在契约测试中断言 code、category、httpStatus、message 与 TypeScript 定义一致；运行目标 pytest 通过
- [x] 1.3 运行 `npm run contracts:typecheck`，确认共享契约类型检查通过

## 2. 报告 claim 标识归一化

- [x] 2.1 为 `ReportClaimDraft.claim_key` 补充模型可见说明（短标识、非结论正文、不超过存储上限），并增加解析前归一化：超长值按字符截断到 120；用 `apps/backend/tests/aiops/test_contracts_and_planning.py` 中断言超长 `claimKey` 不再抛 `ValidationError`
- [x] 2.2 在报告校验阶段对归一化后的重复标识追加稳定后缀，并保证总长度不超过 120；新增单测覆盖"两条不同 claim 归一化后重名仍能分别建立 evidence link"
- [x] 2.3 同步报告提示词中的 `claimKey` 说明，新增/更新提示词与校验器对齐测试；运行 `apps/backend/tests/aiops/test_contracts_and_planning.py` 通过
- [x] 2.4 保留并验证严格校验：引用不存在的 evidence ID、缺少固定标题、缺少逐告警编号仍必须失败并走兜底；运行 `test_contracts_and_planning.py` 与相关 reporting 测试通过

## 3. 报告失败语义

- [x] 3.1 在报告节点保留兜底前的证据评估结果，并按"原本 verified_evidence 但报告失败"选择 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`，其余情况保持 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`
- [x] 3.2 在 `apps/backend/tests/aiops/test_runtime.py` 新增"证据充分但报告模型失败 → 新错误码且信任状态仍为 insufficient_evidence"与"无日志命中 → 仍为证据不足错误码"两条用例并运行通过
- [x] 3.3 确认兜底报告不会被提升为 `verified_evidence`，且既有报告/链接/任务状态测试全部通过

## 4. 集成验证

- [x] 4.1 在 `apps/backend` 运行 `uv run ruff check .` 与 `uv run pyright`，两者均通过
- [x] 4.2 在 `apps/backend` 运行 `uv run pytest`，全部通过（599 passed）
- [x] 4.3 在仓库根运行 `npm run contracts:typecheck` 与 `npm --workspace packages/api-contracts run test`，全部通过（41 passed）
- [x] 4.4 用真实诊断 smoke 验证一次：报告模型返回超长 `claimKey` 时任务不再降级为兜底报告；若本轮模型恰好没有写出超长标识，则以单测覆盖为准并如实记录（任务 `679540e1` succeeded，模型本次 claimKey 仅 23/14 字，超长路径由单测覆盖）
- [x] 4.5 运行 `npx --yes @fission-ai/openspec validate fix-aiops-report-claim-contract --strict`，确认规格无错误

## Workflow follow-up

- 按仓库流程同步 WIKI（`docs/changes/`），并运行 `npm run docs:build`
- 实现与验证完成后，使用 `openspec-verify-change` 复核，再归档该变更
