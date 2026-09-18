## 1. 现状核实

- [ ] 1.1 确认 `DescribeLogContext` 分支抛出的裸 `ValueError` 经 `classify_tool_failure` 后的实际分类与路由（预期 `input_validation` / `retry_same_step`）
- [ ] 1.2 从真实诊断记录中取出该失败的三次 attempt 作为修复前对照证据
- [ ] 1.3 确认 `ClsSearchLogHit.has_context_locator` 的判定依据与现有测试覆盖情况

## 2. 实现

- [ ] 2.1 在 `apps/backend/src/super_ai/aiops/tool_failures.py` 新增表达"数据前置条件不足"的错误类型
- [ ] 2.2 在 `classify_tool_failure` 中把该错误映射为不可重试的 `replan` 路由，并给出明确的中文失败摘要
- [ ] 2.3 在 `apps/backend/src/super_ai/aiops/runtime.py` 的上下文分支改抛该错误，消息中说明缺少定位字段
- [ ] 2.4 确认其它失败分类、退避与 attempt 上限未受影响

## 3. 测试

- [ ] 3.1 单测：该错误分类为 `replan`、不可重试，摘要包含"定位字段"且不含敏感参数值
- [ ] 3.2 集成测试：计划含上下文步骤但命中无定位字段时，只产生一次 failed attempt（不是三次），且不调用参数纠错模型
- [ ] 3.3 回归测试：命中带定位字段时上下文步骤走正常路径，不受本次改动影响
- [ ] 3.4 回归测试：其它 `retry_same_step` / `permanent_failure` 用例保持通过

## 4. 文档

- [ ] 4.1 在运行手册记录该限制：当前日志上传路径产不出 `PkgId`/`PkgLogId`，因此上下文查询不可用
- [ ] 4.2 记录已验证的排查过程（内容形态、存储类型、SDK 版本三条均已排除），避免后人重复调查

## 5. 门禁验证

- [ ] 5.1 在 `apps/backend` 运行 `uv run pytest tests/aiops -q`
- [ ] 5.2 在 `apps/backend` 运行 `uv run pytest -q`
- [ ] 5.3 在 `apps/backend` 运行 `uv run ruff check .` 与 `uv run pyright`
- [ ] 5.4 `openspec validate --all`
- [ ] 5.5 `git diff --check`

## 6. 真实 smoke 与归档

- [ ] 6.1 人工 smoke：重跑一次需要上下文的诊断，确认上下文步骤只失败一次、原因可读，且任务以诚实报告收尾（不得用 mock 结果代替）
- [ ] 6.2 核对实现与 design.md 的偏差；若有偏差，更新 design.md
- [ ] 6.3 按 openspec 校验流程核对任务与规格覆盖情况，确认无 CRITICAL 问题
- [ ] 6.4 归档 change，并用仓库的 wiki-sync 流程同步 `docs/changes/`，确认 VitePress 可构建
