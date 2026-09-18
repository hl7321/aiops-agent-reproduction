## MODIFIED Requirements

### Requirement: Executor 和 Replanner 只承认真实结果

Executor SHALL 只调用本轮真实发现的只读工具，并为每次 attempt 持久化通用 tool audit、步骤状态与 checkpoint。Executor MUST 按其收到的计划逐步执行，不选择工具、不改变步骤顺序、不自行增加步骤；需要改变计划时必须交回 Replanner 处理。

Executor SHALL 在每一步执行前，依据该工具的完整参数说明、整份计划、前面步骤的真实产出与输入告警生成该步参数，并通过该工具真实 schema 的通用入参校验后才调用。成功结果 MUST 先通过工具专属输出 adapter（未登记 adapter 的工具按其产物类型规则处理），再转换为中间产物或规范化证据；失败 MUST 保存安全错误分类并产生 failed 生命周期。

**计划必须执行完毕。** 某个步骤的尝试次数耗尽时，Executor MUST 如实记录该步失败，并 MUST 把进度推进到下一步继续执行；MUST NOT 因为一步失败就把控制权提前交给 Replanner。只有计划中的每一步都被处理过（成功、失败或按规则跳过）之后，才把完整执行结果交给 Replanner。

Replanner SHALL 只做代码级验证：依据完整执行结果与已持久化证据判断是继续执行剩余步骤还是转入报告。其路由 MUST 只取决于进度与证据，MUST NOT 因为"存在失败的步骤"而提前转报告；步骤失败信息保留给报告说明使用。Replanner MUST NOT 调用模型、MUST NOT 改写计划。SearchLog 是当前 Profile 的必需运行证据；DescribeLogContext 失败不得被伪造为成功，但只有本轮 claim 需要时序上下文且没有其他满足策略的独立证据时，才阻止 verified_evidence。

#### Scenario: 工具成功产生证据

- **WHEN** SearchLog 和本轮计划使用的其他证据工具都通过真实调用与各自输出校验
- **THEN** 系统保存对应 audits、attempts、typed evidence 和稳定跨步关联，辅助 query artifact 不冒充运行证据

#### Scenario: 工具失败

- **WHEN** DescribeLogContext 在有界尝试后仍失败
- **THEN** 执行结果如实记录该步失败与其类别；若待支持的时序 claim 最终仍缺少充分证据，报告必须标记 insufficient_evidence 且不可提升，不得伪造上下文成功

#### Scenario: 无上下文仍有充分独立证据

- **WHEN** 当前 claim 不依赖事件前后顺序，或经过校验的多个日志命中与独立指标证据已满足 evidence policy
- **THEN** 系统不因未调用 DescribeLogContext 自动判定失败，但仍须把实际使用的 evidence links 交给报告门禁

#### Scenario: 当前 owner 工具隔离

- **WHEN** 模型试图使用另一个 user 的 MCP connection、知识引用或诊断 task
- **THEN** owner-scoped 查询不返回该资源，执行器不调用该工具且不泄露其存在

#### Scenario: 执行者按计划逐步执行

- **WHEN** Executor 收到一份包含多个步骤的计划
- **THEN** 它按计划给定的工具与顺序逐步执行，不选择其他工具、不调整顺序、不追加计划外的步骤

#### Scenario: 参数来自前序真实产出

- **WHEN** 当前步骤需要前面步骤产生的值
- **THEN** Executor 从前面步骤的真实产出中取值填入，并通过该工具真实 schema 校验后才调用

#### Scenario: 某一步失败后其余步骤继续执行

- **WHEN** 计划中某一步在尝试上限内仍未成功，且其后仍有未执行的步骤
- **THEN** Executor 记录该步失败并把进度推进到下一步，继续执行剩余的每一步，直到计划全部处理完毕才交给 Replanner

#### Scenario: Replanner 不因失败标记提前结束

- **WHEN** 执行结果中存在失败步骤，但计划仍有未执行的步骤
- **THEN** Replanner 继续把控制权交给 Executor，而不是直接转入报告

#### Scenario: Replanner 本轮不改计划

- **WHEN** Replanner 依据执行结果判断证据仍不足以支撑结论
- **THEN** 它按代码规则选择继续执行剩余步骤或转入报告，不调用模型、不生成新计划

### Requirement: 执行结果结构化交付给 Replanner

Executor SHALL 在计划执行完毕后产出一份结构化的执行结果，由代码依据真实调用记录组装，MUST NOT 由模型撰写或总结。执行结果 MUST 覆盖：

- 本轮计划的每一步：工具名、该步实际使用的参数、是否执行、执行顺序。
- 每一步的尝试情况：尝试次数、每次失败的原因摘要，以及该次失败属于"原样重试 / 修正后重试 / 不可重试"中的哪一类。
- 每一步的成功产出：真实返回的安全摘要，MUST NOT 使用与真实结果无关的固定占位文本。
- 产出的证据：按证据类型分组，并标明由哪一步产出。

**执行结果必须结构完整。** 无论执行结果如何——包括所有步骤都失败、没有任何可用证据——Executor MUST 为计划中的每一步产出一条记录，MUST NOT 以"提前中止"的方式交出一份不完整的执行结果。Replanner SHALL 以该执行结果与已持久化证据为唯一判断依据，并据此判定报告可信度。

执行结果中 MUST NOT 出现凭据、Region、TopicId 或其他敏感参数值。

#### Scenario: 全部步骤成功

- **WHEN** 计划的所有步骤都真实成功并产出证据
- **THEN** 执行结果为每一步记录真实参数、成功尝试次数与真实产出摘要，并按类型汇总产出的证据及其来源步骤

#### Scenario: 某一步达到尝试上限

- **WHEN** 某个步骤在尝试上限内仍未成功，且其后仍有未执行的步骤
- **THEN** 执行结果记录该步的尝试次数、每次的失败原因与失败类别，并继续为后续每一步产出记录

#### Scenario: 不可重试错误

- **WHEN** 某个步骤的失败被判定为不可重试
- **THEN** 执行结果记录一次尝试、错误类型和"不可重试"标记，该步不产生第二次调用

#### Scenario: 全部步骤失败

- **WHEN** 计划中的每一步都失败且没有任何可用证据
- **THEN** 执行结果仍覆盖计划的每一步（含未产出证据的标注），并作为 Replanner 判定证据不足的唯一依据

#### Scenario: 执行结果不含敏感值

- **WHEN** 执行结果被交给 Replanner 或写入持久事件
- **THEN** 其中不出现凭据、Region、TopicId 或其他敏感参数的具体取值

### Requirement: 模型失败使用诚实 fallback

当 report LLM 调用、结构校验或固定标题校验失败时，系统 SHALL 根据已持久化告警、计划、步骤和 evidence 生成不可提升的中文执行说明。说明 MUST 标记 `insufficient_evidence` 或 `execution_failed`、生成方式和不确定性，只引用已有 evidence，不得生成新根因、日志、指标、工具结果或伪造 provenance；SearchLog、配置、授权或 runtime 等不可恢复失败 MUST 使诊断失败，条件证据不足不得被 fallback 改写成 verified_evidence。

**诊断的最终状态 MUST 由报告的信任状态决定，而不是由"报告已生成"决定**：

- `verified_evidence` → 任务可标记 `succeeded`。
- `insufficient_evidence` → 任务 MUST NOT 标记 `succeeded`；MUST 以共享契约中表达"证据不足"的既有语义收尾，使客户端能区分"诊断成功"与"未能得出可信结论"。
- `execution_failed` → 任务 MUST 标记 `failed`。

fallback 说明本身 MUST 保持可读，使用户能看到哪些步骤执行过、失败在哪里、为什么结论不可信。

#### Scenario: 报告模型失败但已有证据

- **WHEN** 已收集部分真实 evidence 但报告模型调用失败
- **THEN** 系统可保存不可提升的说明和真实 links，但诊断不以可信报告成功完成，任务状态按信任状态表达而不是 succeeded

#### Scenario: 报告模型失败且无证据

- **WHEN** 模型失败且没有足以支持根因的 evidence
- **THEN** 说明只列告警、已执行步骤和失败原因，不编造任何产品结论或知识资产

#### Scenario: 证据不足不标记成功

- **WHEN** 报告生成成功但信任状态为 insufficient_evidence
- **THEN** 任务最终状态表达"证据不足"而不是 succeeded，且客户端可据此区分"得到可信结论"与"未能得出结论"
