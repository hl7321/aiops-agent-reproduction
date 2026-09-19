# 退役当前数据源不可用的日志上下文工具

> 本变更原地取代了原先"把缺失定位字段当作可处理失败"的方案：实测证明那不是"处理失败"的问题，
> 而是这个工具在当前数据源上**结构上不可能成功**。

## Why

`DescribeLogContext` 有三个必填参数：`Time`、`PkgId`、`PkgLogId`。官方说明写明它们只能来自
`SearchLog` 的原始命中结果。实测发现，**当前日志来源永远产不出后两个字段**：

| 查证 | 结果 |
|---|---|
| SearchLog 的原始返回（绕开本地解析层） | `PkgId: ''`、`PkgLogId: ''`——是 CLS 服务端自己返回的空串 |
| 官方工具说明 | 明确把这两个字段列为必填，并声明来源是 SearchLog 的 Results |
| 上传 SDK（`tencentcloud-cls-sdk-python`） | 唯一的写入方法是 `put_log_raw`，且其 protobuf 里**没有 PkgId 字段** |

也就是说：这不是"我们没传"，而是**这条上传链路结构上无法表达 PkgId**，因此检索结果里不会有它。

后果是 planner 反复规划一个**注定失败**的步骤。真实运行（任务 `ad4a4bd7`）中，该步骤两次失败，
把计划声明成"需要时序上下文"，最终导致报告被判定为证据不足——**而当时已经有 4 条真实日志命中**。

## What Changes

- **退役 `DescribeLogContext`**：在**当前数据源**下把它标记为不可用，对 Planner **完全不可读**——
  不出现在工具目录、不可被规划、也不可被调用。这个判断 MUST 来自"数据源能否满足其前置条件"，
  而不是"是否登记过语义"。
- **告诉 Planner 上下文已经在检索结果里**：当前链路的日志本身携带顺序信息（同一故障的多行日志，
  序号由 `1` 递增），一次普通日志检索就能拿到"之前/之后发生了什么"。Planner 的可读说明 MUST
  表达这一点，避免它再去找一个"专门查上下文"的工具。
- **修正计划校验**：当上下文工具在当前数据源不可用时，计划里的 `requiresTemporalContext` MUST
  不被要求对应一个 DescribeLogContext 步骤；否则模型一旦声明时序需求，它的计划将永远无法通过校验。
- **修正时序证据判定的触发条件**：`requires_temporal_context` 的取值来源是"本轮计划里确实存在
  上下文步骤"。工具退役后该条件恒为假，时序分支不再被虚假激活，多条按序排列的日志命中即可满足
  非时序证据规则。判据本身不改。
- **文档化备选方案**：如果将来换了日志来源（能产出定位字段，或首次检索过窄需要二次扩宽），
  可以用"第二次日志检索"按同一链路标识取上下文作为替代。**本次不实现**，只写进文档。

非目标：

- 不换上传路径去强行产出 `PkgId`：官方 SDK 没有可用替代入口，控制台采集路径不在本仓库可控范围。
- 不改证据充分性判据本身（`verified_evidence` / `insufficient_evidence` 的规则不变）。
- 不改 attempt 上限、退避策略与其它失败分类。
- 不处理"指标类工具在日志主题上不可用"（同一类问题，但属另案，见 Impact）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: 工具可用性必须反映数据源能否满足其前置条件；上下文工具在当前数据源退役；Planner 可读说明必须说明上下文已在检索结果中。
- `aiops-diagnosis-and-evidence`: 计划校验不再强制"声明时序需求就必须有上下文步骤"；时序证据判定的触发条件随工具退役一并修正。

## Impact

**后端代码**

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/tool_policy.py` | 新增"数据源不满足前置条件"的退役标记；`DescribeLogContext` 在目录与 registry 中都不再出现 |
| `apps/backend/src/super_ai/aiops/planning.py` | 计划校验：上下文工具不可用时不再要求对应步骤；Planner 提示词说明上下文已在检索结果中 |
| `apps/backend/src/super_ai/aiops/runtime.py` | 时序证据判定的触发条件与目录一致；退役工具的调用路径不可达 |
| `apps/backend/src/super_ai/aiops/evidence_policy.py` | 预期不改（判据不变），仅确认时序分支不再被虚假激活 |

**测试**：新增"退役工具不出现在目录/registry""声明时序需求但工具不可用时计划仍合法""多条有序 log_hit 满足非时序证据"的用例；更新引用该工具的既有用例。

**文档**：把"第二次日志检索取上下文"写成可追溯的备选方案。

**相关但不在本次范围**：真实 smoke 同时发现 `QueryRangeMetric` 因"topic is not metric topic"失败——
它与本变更是同一类问题（工具本身正确、数据源不满足前置条件），是否一并退役需要单独决策。
