# Tasks

## 1. 最小告警摘要与 executor 上下文

- [x] 1.1 新增最小告警摘要构造：只保留 alertName/service/severity/startsAt/关键 labels/summary/rootCause（有界），并加单测断言不含 rawContext/fingerprint/receivers
- [x] 1.2 重写 `_step_argument_context`，只输出「工具说明 + 计划 + 告警摘要 + 需要的前序产出 + 上一次错误」，并加 runtime 测试断言不再包含全部证据
- [x] 1.3 保留 planner 与 report 的现有上下文构造不变；加测试断言 planner 仍能看到完整告警与 SOP

## 2. 计划自包含与按需前序产出

- [x] 2.1 更新 planner 提示词：每一步 purpose 必须写出执行所需业务字段（服务名、logger、异常类型、要拿到的信息），并更新提示词测试
- [x] 2.2 实现"默认只传上一步产出、单段上限 2000 字"的规则；SearchLog 步骤默认不传前序证据（Query/From/To/Region/TopicId 已服务端绑定），并加单测
- [x] 2.3 用现有 DescribeTopics / TextToSearchLogQuery / SearchLog 场景回归，确保参数与证据结果不变

## 3. 工具目录 JSON 与约束

- [x] 3.1 `_catalog_payload` 改为 `json.dumps(..., ensure_ascii=False)`，并加测试断言输出可被 `json.loads` 解析、不含 Python `None`/`True`/单引号
- [x] 3.2 `_visible_property` 保留 `minimum`/`maximum`/`minLength`/`maxLength`/`pattern`/`additionalProperties`/`examples`，加约束保留测试
- [x] 3.3 回归服务端注入字段隐藏：SearchLog 的 Region/TopicId/From/To 仍不出现在模型可见 schema

## 4. 集成验证

- [x] 4.1 在 `apps/backend` 运行 `uv run ruff check .` 与 `uv run pyright`
- [x] 4.2 在 `apps/backend` 运行 `uv run pytest`（613 passed）
- [x] 4.3 真实 smoke：任务 `4040db5b` 159 秒 succeeded；executor 单步从 6.4~7.1k 降到 2.5~3.0k 字符，prompt 从 plus 基线约 27.6k 降到 24.3k，且 executor 提示词不含 rawContext/fingerprint
- [x] 4.4 运行 `npx --yes @fission-ai/openspec validate slim-aiops-execution-context --strict`

## Workflow follow-up

- 按仓库流程同步 WIKI（`scripts/sync_wiki.py active`），并运行 `npm run docs:build`
- 实现与验证完成后，使用 `openspec-verify-change` 复核，再归档该变更
