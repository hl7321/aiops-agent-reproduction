## Context

动机见 `proposal.md`。这里是决定实现方式的现状与约束。

**当前执行与路由**（`apps/backend/src/super_ai/aiops/runtime.py`）：

```python
# executor：只有成功才推进指针
state = {**state, "next_position": state["next_position"] + 1, "last_error": None}

# executor：尝试耗尽的出口（指针不动）
state = {**state, "last_error": failure.safe_message}

# replanner：一旦有失败标记就直接收工
if remaining and not state.get("last_error"):
    → executor
else:
    → report
```

这条 `last_error` 判断原本是**防死循环**的保险：executor 耗尽尝试后不推进指针，Replanner 若仍把控制权交回去，同一个步骤会被无限重跑。

**当前报告提示词与校验器**：

| | 要求 |
|---|---|
| 校验器 `reporting.py` | 字面量 `详情：` / `症状：` / `日志证据：` / `根因结论：`（全角冒号） |
| 提示词 `planning.py` | "（详情/症状/日志证据/根因结论）"——只给字段名，未说明渲染形式 |

离线复现该次失败：模型返回 2253 字、7 条 claims 的完整 markdown，**仅因标签写法不同被判"缺少固定中文字段"**。

**当前任务终态**：report 节点写完报告后无条件 `transition_task(..., "succeeded")`，与报告信任状态无关。

**约束**：诊断状态取值集合 `accepted|running|succeeded|failed|cancelled` 有数据库 CHECK 约束；不新增状态可避免 Alembic 迁移。共享错误目录是既有的可扩展机制。

## Goals / Non-Goals

**Goals:**

- 让"计划被完整处理"成为交给 Replanner 的前提，而不是"直到某一步失败"。
- 让报告的结构要求对模型是**可照抄**的，而不是靠猜。
- 让任务终态表达"诊断是否得出可信结论"，而不是"流程是否走完"。

**Non-Goals:**

- 不改证据充分性判据、报告固定结构、结构校验严格程度。
- 不新增诊断状态取值，不引入迁移。
- 不解决 `DescribeLogContext` 缺少定位字段的问题，也不改"恰好一个 SearchLog"的 Profile 规则。

## Decisions

### D1 · Executor 失败后继续推进进度指针

**选择**：某一步尝试耗尽时，Executor 记录该步失败，并把 `next_position` 推进到下一步，继续处理剩余步骤。

**备选：保持现状（失败即交出控制权）。** 否掉——它偏离既定设计，实测导致 `QueryRangeMetric` 整步未执行，而该步本可能提供指标证据。

**死循环防护**：指针持续推进，计划长度有上限（8 步），因此循环次数天然有界；原先那条 `last_error` 保险不再需要，可以删除。

### D2 · Replanner 路由只看进度与证据

**选择**：Replanner 依据"是否还有未处理的步骤"与已持久化证据决定继续或转报告；步骤失败信息保留给报告说明使用，不影响路由。

**备选：保留"有失败即转报告"。** 否掉——这正是本次要修的偏离。

### D3 · 报告提示词与校验器逐字对齐

**选择**：提示词以**字面量**给出每个固定标签（含全角冒号），并附一份完整的结构示例供模型照抄。

**备选：放宽校验器，接受半角冒号或自定义标签。** 否掉——报告固定中文结构是产品要求（也是 spec 的一部分），放宽会让报告结构与质量都不可控；问题出在"要求没说清"，不是"要求太严"。

**备选：在提示词里只列字段名，靠模型自然语言能力推断。** 已被实测否掉——模型确实没推断出全角冒号这个约定。

### D4 · 任务终态由报告信任状态决定

| 信任状态 | 任务终态 |
|---|---|
| `verified_evidence` | `succeeded` |
| `insufficient_evidence` | `failed` + 专用稳定错误码 |
| `execution_failed` | `failed`（现有语义） |

**备选 A：新增状态 `inconclusive`。** 语义最准，但要改数据库 CHECK 约束（需 Alembic 迁移）、共享契约状态枚举与前端状态分支。本次不采用以控制改动面。

**备选 B（采用）：复用 `failed` + 专用稳定错误码**（例如 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`）。理由：项目已有"稳定错误目录"这一机制，正合此用；无迁移；前端复用既有 failed 展示；`failureCode` 让"系统故障"与"证据不足"可区分。

**备选 C：保持 `succeeded`，仅让前端按 `report.trustState` 显示。** 否掉——后端状态仍会误导其它消费者，而问题的本质就是"状态没有表达真实结论"。

**连带影响（正向）**：案例沉淀要求任务为 `succeeded`，因此"证据不足"的诊断将不再进入沉淀链路——与既有设计意图一致。

### D5 · fallback 报告与其证据链保持可读

**选择**：兜底报告继续保存，报告中已收集的真实证据链继续保留；失败的是"结论可信度"，不是"可观测性"。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 计划跑完会让失败场景的调用数上升（最坏 8 步 × 2 次） | 步数上限 8 不变；分类已把"不可重试"的拦在一次以内 |
| 失败步骤变多会让报告上下文变长 | 执行结果按步给安全摘要，不塞原始日志全文 |
| "证据不足"落到 `failed` 会改变现有依赖 `succeeded` 的下游（案例沉淀） | 这正是期望行为；在 tasks 中显式补回归测试确认案例不再从证据不足任务沉淀 |
| 前端可能把"证据不足"直接显示成系统故障 | 复用 failed 展示的同时，前端按 `failureCode` 给出"证据不足"措辞；属于实现细节，见 Open Questions |

## Migration Plan

1. **无数据迁移**：状态取值集合不变，仅改变写入 `succeeded` 的条件。
2. **错误目录扩展**：`super_ai/api_contracts.py` 与 `packages/api-contracts` 同步新增"证据不足"稳定错误码，并补合同测试。
3. **实施顺序**：先补测试（期望新行为失败）→ 改 executor 推进逻辑 → 删 Replanner 的失败提前退出 → 改报告提示词 → 改任务终态判定 → 同步前端展示。
4. **验证**：后端全量 pytest + Ruff + strict Pyright；契约 typecheck 与测试；`openspec validate --all`；`git diff --check`；真实 smoke 跑一次，核对"某步失败后其余步骤仍执行""报告不再因标签写法回退""任务终态与信任状态一致"。
5. **回滚**：本变更落在独立 commit，回滚即 revert；无迁移，回滚不需要数据修复。

## Open Questions

- AIOps 工作区是否需要为"证据不足"设计独立的视觉状态（而不是复用失败样式）？属于展示细节，不改变规格与任务拆分，实现时确认。
