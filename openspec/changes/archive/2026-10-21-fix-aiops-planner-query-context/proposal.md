# Proposal

## Why

现有规格要求 Planner 依据“输入告警、可选 query、SOP 与真实工具目录”生成计划，但运行时只把告警和证据交给 Planner，没有直接提供 `task.query`。纯 query 诊断之所以偶尔能跑通，是因为知识检索恰好把 query 中相同的信息带进了 SOP；一旦没有 SOP 或 SOP 与用户问题不一致，Planner 实际上看不到用户目标，只能猜测或依赖错误背景。

## What Changes

- 把非空用户 query 作为独立、明确的 Planner 输入，与告警、SOP、工具目录一起传入。
- 明确诊断优先级：
  - 有 query 时，query 是用户诊断目标，告警和 SOP 提供范围、时间与领域知识；
  - 没有 query 但有告警时，以告警为诊断目标；
  - query 与告警同时存在时，两者都可见，不得让 SOP 替代 query。
- 更新 Planner 提示语义：SOP 只能辅助计划，不能成为用户意图的唯一来源。
- 要求 Planner 在步骤用途中保留 query 的关键诊断目标，供最小上下文的 Executor 正确执行。
- 增加纯 query、仅告警、query+告警三类上下文与计划回归测试。

非目标：

- 不修改 query 的正则化、API 入参、DTO、SSE、SQLite 或前端；
- 不修改 SearchLog 时间窗规则；
- 不把完整对话历史或全部证据塞给 Executor；
- 不修改 SOP 检索、工具发现或工具参数归属。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `aiops-diagnosis-and-evidence`：明确 Planner 对 query 与告警的输入顺序和诊断优先级，SOP 不得替代用户 query。
- `schema-aware-aiops-tool-execution`：Planner 上下文必须显式包含非空 query，同时继续对 Executor 保持最小可见范围。

## Impact

| 区域 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/runtime.py` | Planner 上下文组装增加可选 query |
| `apps/backend/src/super_ai/aiops/planning.py` | Planner 提示词明确 query、告警与 SOP 的职责 |
| `apps/backend/tests/aiops/` | 覆盖三种输入组合及 SOP 缺失场景 |
| API / DTO / 数据库 / 前端 | 无契约或数据结构改动 |
