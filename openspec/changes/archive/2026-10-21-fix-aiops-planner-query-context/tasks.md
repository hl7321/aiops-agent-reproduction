# Tasks

## 1. Planner 输入与提示语义

- [x] 1.1 在 Planner 上下文组装中加入可选 query，输出独立 `用户问题` 标签；验证纯 query 与仅告警两种上下文字符串均符合预期
- [x] 1.2 更新 Planner 系统提示，明确 query、告警、SOP 的职责与优先级，并验证提示内容包含 query 优先、SOP 不得替代 query 的规则
- [x] 1.3 要求步骤用途保留执行所需 query 目标；补模型结构化输出或上下文测试，验证计划用途包含纯 query 的关键对象

## 2. Runtime 回归

- [x] 2.1 runtime 在 Planner 调用时传入 `task.query`，并验证 Report 等其他调用不会因该参数意外扩大上下文
- [x] 2.2 补纯 query + alerts=[] + 无 SOP 的 runtime 测试，验证 Planner 实际收到 query 且计划不依赖 SOP 信息
- [x] 2.3 补 query+告警测试，验证 Planner 同时收到两者并以 query 定义目标；运行 `test_contracts_and_planning.py` 与 `test_runtime.py`

## 3. 真实 smoke

- [x] 3.1 提交一次知识库无对应 SOP 的纯 query 诊断，确认计划用途直接引用 query 中的独有目标，而不是从 SOP 反推
- [x] 3.2 检查该任务的计划与步骤记录，确认 query 可见性没有改变 SearchLog 时间窗、工具参数注入或 Executor 最小上下文语义

## 4. 门禁与文档

- [x] 4.1 后端运行 `uv run ruff check .`、`uv run pyright`、`uv run pytest`
- [x] 4.2 运行 `npx --yes @fission-ai/openspec validate fix-aiops-planner-query-context --strict`
- [x] 4.3 同步 active WIKI 并运行 `npm run docs:build`

## Workflow follow-up

- 实现和验证完成后使用 `openspec-verify-change` 复核。
- 用户确认后归档、提交并推送。
- 把实际改动、验证结果和剩余问题同步到 Obsidian。
