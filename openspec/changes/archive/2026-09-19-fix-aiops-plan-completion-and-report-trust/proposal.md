# 让诊断计划跑完并按报告信任状态判定任务结果

## Why

真实运行（任务 `ad4a4bd747854aa4add3d9650f411682`）暴露三个互相牵连的问题，它们让一次**已经拿到 4 条真实日志证据**的诊断，最终以兜底报告和 `succeeded` 收场。

**问题一：一步失败就跳过后面所有步骤。** 这偏离了本能力的既定设计——计划应当**完整执行完毕**再交给 Replanner 统一判断。实际实现里，executor 只有在步骤成功时才推进进度指针；尝试耗尽时不推进，于是 Replanner 只能靠 `last_error` 判定"别再回 Executor"，直接转报告。结果：第 3 步 `DescribeLogContext` 失败后，**第 4 步 `QueryRangeMetric` 一次都没跑**——它本来可能拿到指标证据。

**问题二：报告提示词与结构校验对不上。** 校验器要求报告里出现字面量 `详情：`、`症状：`、`日志证据：`、`根因结论：`（带全角冒号），而提示词只写了"（详情/症状/日志证据/根因结论）"——**没有说明必须渲染成全角冒号形式**。模型按自己的习惯写成 `- **告警名称**: ...`，被判定"缺少固定中文字段"，报告直接走兜底。离线复现确认：模型返回 2253 字结构完整的 markdown、7 条 claims，**只是标签写法与校验器不一致**。

**问题三：任务状态与报告可信度脱钩。** 现在"流程跑完"就等于 `succeeded`，哪怕报告是兜底模板、信任状态是 `insufficient_evidence`。用户界面上看到的是"诊断完成"，但拿到的是一份写着"证据不足"的模板——**状态没有表达真实结论**。

## What Changes

- **计划必须执行完毕。** Executor 在某个步骤尝试耗尽后，MUST 如实记录该步失败并**继续推进到下一步**，不得把控制权提前交出。只有计划中所有步骤都被处理过（成功、失败或跳过）之后，才把执行结果交给 Replanner。
- **Replanner 的路由只看计划进度与证据，不再看"是否有步骤失败过"。** 删除当前"`last_error` 非空即转报告"的提前退出条件；该标记保留为报告说明用的信息，不再影响路由。
- **执行结果必须结构完整。** 即使全部步骤都失败，Executor MUST 产出一份覆盖每一步的结构化执行结果（工具名、实际参数、尝试次数、每次失败原因与类别、是否有产出），再交给 Replanner 判断报告可信度。
- **报告提示词与校验器逐字对齐。** 提示词 MUST 以字面量形式给出每个固定标签（含全角冒号），并附一份完整结构示例，使模型可以照抄结构而不是猜测写法。
- **任务最终状态由报告信任状态决定。** `verified_evidence` → `succeeded`；`insufficient_evidence` → 进入既有的证据不足语义，不再标记 `succeeded`；`execution_failed` → `failed`。前端展示与共享契约同步该语义。

非目标：

- 不改证据充分性判断规则本身（`verified_evidence` / `insufficient_evidence` / `execution_failed` 的判据不变）。
- 不改报告固定中文结构，也不放宽结构校验。
- 不解决 `DescribeLogContext` 缺少定位字段的问题（另案讨论），也不改变"计划恰好包含一个 SearchLog"的 Profile 规则。
- 不恢复 Replanner 的换计划能力。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `aiops-diagnosis-and-evidence`: 计划必须完整执行完毕后再交给 Replanner；执行结果必须结构完整；报告提示词与结构校验逐字对齐；任务最终状态由报告信任状态决定。
- `api-and-sse-contracts`: 任务状态与前端展示按报告信任状态区分"成功"与"证据不足"。

## Impact

**后端代码**

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/runtime.py` | Executor 失败后继续推进进度；删除 Replanner 的 `last_error` 提前退出；报告节点按信任状态决定任务终态 |
| `apps/backend/src/super_ai/aiops/planning.py` | 报告提示词改为逐字标签 + 完整结构示例 |
| `apps/backend/src/super_ai/aiops/evidence_policy.py` | 预期不变（判据不改）；仅在信任状态需要显式传递时最小调整 |

**状态语义**：`diagnostic_tasks.status` 的取值集合不变，改变的是**何时**写入 `succeeded`——从"报告已生成"改为"报告可信"。

**契约与前端**：若前端需要区分"成功"与"证据不足"，同步 `packages/api-contracts` 与 AIOps 工作区展示；SSE 事件目录不变。

**测试**：`test_runtime.py`、`test_contracts_and_planning.py` 需同步更新；新增"任一步失败后其余步骤仍执行""执行结果结构完整""报告标签逐字对齐""信任状态决定任务终态"的用例。
