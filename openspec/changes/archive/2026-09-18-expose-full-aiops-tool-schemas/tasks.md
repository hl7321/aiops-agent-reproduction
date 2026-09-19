## 1. 现状核实

- [x] 1.1 记录当前模型可见的工具目录内容（字段只剩 type），作为修复前对照证据
- [x] 1.2 记录当前真实运行中模型填错的参数样例（例如编造的 TopicId、秒级时间戳、模板占位符 Query），作为"说明书不全导致猜测"的证据
- [x] 1.3 列出 `normalize_search_log_arguments`、`build_text_to_search_log_query_input` 与 runtime 中所有补偿性逻辑的完整清单，确认删除范围
- [x] 1.4 确认 `Region`/`TopicId` 从 properties 与 required 同时移除后，`validate_runtime_tool_input` 仍能通过官方 schema 校验

## 2. 完整参数说明书

- [x] 2.1 在 `apps/backend/src/super_ai/aiops/tool_policy.py` 用完整 schema 投影替换 `_safe_schema_summary`：保留 description、type、enum、format、default 与 required
- [x] 2.2 在投影中移除服务端权威字段（`Region`、`TopicId`），并同步从 required 列表移除
- [x] 2.3 确认 `planning._catalog_payload` 输出的目录对 Planner 与 Replanner 一致
- [x] 2.4 为字段说明设定长度上限，保证提示词体积可控，但不丢弃字段用途与枚举

## 3. 删除补偿性兜底

- [x] 3.1 删除 `normalize_search_log_arguments` 中的键名别名映射
- [x] 3.2 删除缺失时间范围与缺失查询的默认值填充
- [x] 3.3 删除秒级时间戳自动换算
- [x] 3.4 删除非法时间窗口自动重置
- [x] 3.5 删除 `build_text_to_search_log_query_input` 中的 `Text`/`Prompt`/`Question` 别名
- [x] 3.6 保留 Region/TopicId 注入与官方 schema 校验；把必填检查改为直接报错，不再先补默认值
- [x] 3.7 确认 `runtime.executor` 的调用前准备只剩"注入服务端权威字段 + 校验"

## 3A. 放行只读辅助工具

- [x] 3A.1 在 `tool_policy.py` 为 policy 条目增加"证据型 / 只读辅助型"的区分，并登记官方只读工具（时间戳转换、`DescribeIndex`、`DescribeAlarms`、`DescribeTopics` 等）
- [x] 3A.2 确认具有写副作用的工具仍然无法进入 policy 与计划
- [x] 3A.3 让 `tool_adapters` 接受只读辅助工具：产物以 `query_artifact` 类别落库，进入模型可见上下文，但不计入证据充分性判断
- [x] 3A.4 收紧 `runtime._latest_query_artifact()`：只接受来源为 query-builder 工具的产物，避免辅助产物被误当成查询
- [x] 3A.5 确认模型可见的工具目录包含这些辅助工具及其完整参数说明

## 4. 测试

- [x] 4.1 单测：模型可见的搜索日志参数说明包含字段用途、类型与必填项，且不包含 Region/TopicId
- [x] 4.2 单测：模型参数缺必填项、类型不符、时间单位为秒、字段名不在官方 schema 时，直接以校验错误失败，且不发生静默补齐或换算
- [x] 4.3 单测：模型提供 Region/TopicId 时被忽略并以本地配置注入值为准
- [x] 4.4 回归测试：更新原先断言默认时间窗、单位换算与别名映射的既有用例，使其与新契约一致
- [x] 4.5 回归测试：工具输入校验、计划级策略校验与 retry/replan/permanent 路由判定保持通过
- [x] 4.6 单测：只读辅助工具进入 policy 与目录；写副作用工具仍被拒绝
- [x] 4.7 单测：辅助工具产物落库后不出现在证据充分性判断的支撑集合里，但能被 Replanner 上下文读取
- [x] 4.8 单测：辅助产物含 `Query` 字段时不会被 `_latest_query_artifact()` 误用

## 5. 门禁验证

- [x] 5.1 在 `apps/backend` 运行 `uv run pytest tests/aiops -q`
- [x] 5.2 在 `apps/backend` 运行 `uv run pytest -q`
- [x] 5.3 在 `apps/backend` 运行 `uv run ruff check .` 与 `uv run pyright`
- [x] 5.4 `openspec validate --all`
- [x] 5.5 `git diff --check`

## 6. 真实 smoke 与归档

- [x] 6.1 人工 smoke：重跑一次真实诊断，确认模型在只看完整说明书的条件下自行给出合法的时间窗口与查询，SearchLog 命中真实日志
- [x] 6.2 记录模型在新说明下是否仍出现参数错误，以及错误类型；若模型无法稳定填出合法时间窗，如实记录并评估是否需要回退单条默认值
- [x] 6.3 核对实现与 design.md 的偏差；若有偏差，更新 design.md
- [x] 6.4 按 openspec 校验流程核对任务与规格覆盖情况，确认无 CRITICAL 问题
- [x] 6.5 归档 change，并用仓库的 wiki-sync 流程同步 `docs/changes/`，确认 VitePress 可构建
