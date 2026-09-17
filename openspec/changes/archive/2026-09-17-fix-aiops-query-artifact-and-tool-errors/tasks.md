## 1. 影响面核实

- [x] 1.1 检索 `_extract_generated_query`、`parse_text_to_search_log_query_result` 的调用点，确认反转义的最佳落点与影响范围
- [x] 1.2 检索 `classify_tool_failure` 的全部调用点，确认签名变更的影响面（预期只有 `runtime.executor` 与既有测试）
- [x] 1.3 用真实 MCP 返回复现当前行为，记录"修复前产出带字面量转义的查询"作为对照证据

## 2. 查询反转义

- [x] 2.1 在 `apps/backend/src/super_ai/aiops/cls_tool_adapters.py` 增加内部反转义处理：优先按 JSON 字符串解码，失败时退化为替换已知转义序列，无转义时保持原样
- [x] 2.2 在 `_extract_generated_query()` 返回前应用该处理，使产出的查询可直接执行
- [x] 2.3 确认 `QueryArtifact` 的既有校验（非空、长度上限）在反转义后仍然成立

## 3. 失败摘要可见且脱敏

- [x] 3.1 让 `classify_tool_failure()` 接收调用参数（或等价脱敏上下文），保持既有参数默认值以兼容现有调用
- [x] 3.2 在 `apps/backend/src/super_ai/aiops/tool_failures.py` 中保留服务端消息的有界摘要：先过 `redact_error()`，再按敏感参数键（`Region`、`TopicId` 等）抹掉取值
- [x] 3.3 确认 `category`、`route`、`retryable`、`delay` 的判定逻辑未变，仅摘要内容变化
- [x] 3.4 在 `runtime.executor` 的失败分支传入当次调用参数，使脱敏上下文可得

## 4. 测试

- [x] 4.1 adapter 单测：含围栏与转义的返回 → 产出可执行查询；无转义的返回 → 原样保留；含 `\d` 这类合法反斜杠 → 不误伤
- [x] 4.2 失败分类单测：服务端消息被保留为有界摘要；`Region`/`TopicId` 的取值不出现在结果里；凭据类值被抹掉
- [x] 4.3 回归测试：`retry_same_step` / `replan` / `permanent_failure` 的路由判定与既有用例保持一致
- [x] 4.4 端到端回归：`SearchLog` 的失败仍写入 step、tool audit 与持久事件，且内容为脱敏摘要

## 5. 门禁验证

- [x] 5.1 在 `apps/backend` 运行 `uv run pytest tests/aiops -q`
- [x] 5.2 在 `apps/backend` 运行 `uv run pytest -q`（契约与错误路径是横切关注点，跑全量）
- [x] 5.3 在 `apps/backend` 运行 `uv run ruff check .` 与 `uv run pyright`
- [x] 5.4 `openspec validate --all`
- [x] 5.5 `git diff --check`

## 6. 真实 smoke 与归档

- [x] 6.1 人工 smoke：重跑一次真实诊断，确认 SearchLog 用模型生成的查询即可命中（不再依赖兜底查询），且失败摘要可读（不得用 mock 结果代替）
- [x] 6.2 核对实现与 design.md 的偏差；若有偏差，更新 design.md
- [x] 6.3 运行 openspec 校验流程核对任务与规格覆盖情况，确认无 CRITICAL 问题
- [x] 6.4 归档 change，并用仓库的 wiki-sync 流程同步 `docs/changes/`，确认 VitePress 可构建
