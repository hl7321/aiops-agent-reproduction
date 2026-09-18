## ADDED Requirements

### Requirement: 执行结果结构化交付给 Replanner

Executor SHALL 在计划执行完毕后产出一份结构化的执行结果，由代码依据真实调用记录组装，MUST NOT 由模型撰写或总结。执行结果 MUST 覆盖：

- 本轮计划的每一步：工具名、该步实际使用的参数、是否执行、执行顺序。
- 每一步的尝试情况：尝试次数、每次失败的原因摘要，以及该次失败属于"原样重试 / 修正后重试 / 不可重试"中的哪一类。
- 每一步的成功产出：真实返回的安全摘要，MUST NOT 使用与真实结果无关的固定占位文本。
- 产出的证据：按证据类型分组，并标明由哪一步产出。

执行结果中 MUST NOT 出现凭据、Region、TopicId 或其他敏感参数值。Replanner SHALL 以该执行结果与已持久化证据为唯一判断依据。

#### Scenario: 全部步骤成功

- **WHEN** 计划的所有步骤都真实成功并产出证据
- **THEN** 执行结果为每一步记录真实参数、成功尝试次数与真实产出摘要，并按类型汇总产出的证据及其来源步骤

#### Scenario: 某一步达到尝试上限

- **WHEN** 某个步骤在两次尝试后仍未成功
- **THEN** 执行结果记录该步的尝试次数、每次的失败原因与失败类别，并明确标注该步未产出证据

#### Scenario: 不可重试错误

- **WHEN** 某个步骤的失败被判定为不可重试
- **THEN** 执行结果记录一次尝试、错误类型和"不可重试"标记，该步不产生第二次调用

#### Scenario: 执行结果不含敏感值

- **WHEN** 执行结果被交给 Replanner 或写入持久事件
- **THEN** 其中不出现凭据、Region、TopicId 或其他敏感参数的具体取值

## MODIFIED Requirements

### Requirement: Planner 先获取 SOP 并发现 owner 工具

Planner SHALL 先以当前 owner scope 调用 `knowledge_retrieval` 检索 SOP，再发现当前 user enabled MCP connections 的真实工具。Planner MUST 只根据输入告警、可选 query、SOP 引用，以及本轮真实发现的只读工具的名称、描述和完整参数 schema 生成有界计划；工具集合 MUST NOT 再与静态名单取交集。

Planner MUST NOT 输出任何工具参数值：计划生成时后续步骤的真实产出尚不存在，参数由 Executor 在该步骤执行时提供。没有 SOP 结果 MAY 继续，但不得伪造 SOP。当前 CLS Profile MUST 恰好包含一个 SearchLog；只要计划包含日志检索，MUST 在它之前包含恰好一个 query-builder 步骤，与该次诊断是否携带用户原始查询无关。只有结论需要日志时序且命中提供定位字段时才要求 DescribeLogContext。其他步骤也 MUST 引用本轮真实发现的只读工具；模型输出不得扩大 owner、工具或权威参数权限。

#### Scenario: 有 SOP 且有 SearchLog

- **WHEN** owner 知识库返回 SOP 且本轮发现可用的 SearchLog
- **THEN** 最终计划保存 SOP 引用并恰好包含一个真实 SearchLog，且该 SearchLog 之前存在一个 query-builder 步骤

#### Scenario: 没有 SOP

- **WHEN** owner-scoped knowledge retrieval 返回空结果但存在可用的 SearchLog
- **THEN** Planner 可继续生成有界计划，并明确记录没有 SOP 证据而不是生成虚假引用

#### Scenario: 缺少 SearchLog 工具

- **WHEN** 当前 owner 的真实发现结果中缺少当前 Profile 必需的 SearchLog
- **THEN** 任务以稳定 SearchLog 工具缺失错误失败；缺少条件工具只有在本轮条件成立时才构成对应能力不足

#### Scenario: 模型建议未注册工具

- **WHEN** Planner 输出真实发现之外的只读工具、多个 SearchLog，或违反本轮成立的条件依赖
- **THEN** 系统在最多三次内反馈脱敏校验错误要求修正，仍无效则失败且绝不调用该计划

#### Scenario: 计划不携带参数

- **WHEN** Planner 生成任何一份可执行计划
- **THEN** 计划中的每一步只包含工具名、用途与顺序，不含任何参数值

### Requirement: Executor 和 Replanner 只承认真实结果

Executor SHALL 只调用本轮真实发现的只读工具，并为每次 attempt 持久化通用 tool audit、步骤状态与 checkpoint。Executor MUST 按其收到的计划逐步执行，不选择工具、不改变步骤顺序、不自行增加步骤；需要改变计划时必须交回 Replanner 处理。

Executor SHALL 在每一步执行前，依据该工具的完整参数说明、整份计划、前面步骤的真实产出与输入告警生成该步参数，并通过该工具真实 schema 的通用入参校验后才调用。成功结果 MUST 先通过工具专属输出 adapter（未登记 adapter 的工具按其产物类型规则处理），再转换为中间产物或规范化证据；失败 MUST 保存安全错误分类并产生 failed 生命周期。

Replanner 在本轮 SHALL 只做代码级验证：依据执行结果与已持久化证据判断是继续执行剩余步骤还是转入报告，MUST NOT 调用模型、MUST NOT 改写计划。SearchLog 是当前 Profile 的必需运行证据；DescribeLogContext 失败不得被伪造为成功，但只有本轮 claim 需要时序上下文且没有其他满足策略的独立证据时，才阻止 verified_evidence。

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

#### Scenario: Replanner 本轮不改计划

- **WHEN** Replanner 依据执行结果判断证据仍不足以支撑结论
- **THEN** 它按代码规则选择继续执行剩余步骤或转入报告，不调用模型、不生成新计划

### Requirement: 报告使用固定中文结构和真实 provenance

报告生成器 SHALL 只把输入告警、真实 SOP 引用、最终计划、执行结果和已持久化且通过合同校验的 evidence 提供给模型，并要求输出既有固定中文 Markdown 结构。每个关键结论 MUST 建立 report_evidence_link。报告 MUST 标记 `verified_evidence|insufficient_evidence|execution_failed` 信任状态；只有当前 Profile 的必需能力和每个 claim 的 evidence policy 均满足、所有确定性 claim 有真实链接且 `uncertainty=false` 时才能标记 `verified_evidence`。工具数量或单一工具名称不得单独决定可信状态。报告持久化不得自动触发案例或知识写入。

#### Scenario: 多告警报告

- **WHEN** 任务包含多条告警且每条确定性结论都有完整真实必需证据
- **THEN** 报告保持固定结构、关键结论链接现有 evidence id，并标记 verified_evidence

#### Scenario: 证据不足

- **WHEN** 允许生成说明但证据不足以支持根因
- **THEN** 内容标记 uncertainty 和 insufficient_evidence，不产生可提升的确定性结论

#### Scenario: provenance 指向真实记录

- **WHEN** 客户端读取 evidence-chain
- **THEN** 每个 report link 指向同 owner、同 diagnostic task 的现有 evidence，不能链接任意或跨租户记录

#### Scenario: 成功报告触发自动 case

- **WHEN** 任意信任状态的 report 被持久化
- **THEN** report 节点不自动创建 case、知识文档或 index task，知识提升等待独立人工认可流程

#### Scenario: 报告使用执行结果说明未完成步骤

- **WHEN** 执行结果中存在未执行或失败的步骤
- **THEN** 报告依据该执行结果如实说明哪些步骤未完成及其失败类别，不虚构执行成功
