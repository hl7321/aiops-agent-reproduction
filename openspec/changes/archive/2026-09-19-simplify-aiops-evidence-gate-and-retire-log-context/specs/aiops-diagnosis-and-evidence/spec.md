## ADDED Requirements

### Requirement: 证据充分性以真实日志命中为锚点

系统 SHALL 以"本轮是否拿到真实 `log_hit` 证据"作为证据充分性的唯一锚点，MUST NOT 把当前数据源无法提供的证据形态或数量组合写成必要条件。判据只保留三档：

1. **执行失败**：必需的日志检索真实失败（且不是"空结果"）并且没有任何日志命中。
2. **证据不足**：一条真实日志命中都没有。
3. **证据充分**：拿到了至少一条真实日志命中。

删除"需要时序时必须存在日志上下文证据"与"多源组合（若干条命中同时要有指标）"这类要求。日志上下文的顺序信息在当前数据源由检索结果自身携带，因此不得再要求一个独立工具产物；指标只有在数据源真实提供时才参与判断，MUST NOT 作为必要条件。

判据 MUST 由真实持久化的证据与步骤记录计算，MUST NOT 取决于模型自述。

#### Scenario: 单条真实日志命中即视为证据充分

- **WHEN** 本轮只拿到一条真实 `log_hit`，没有指标、也没有日志上下文产物
- **THEN** 证据状态为 `verified_evidence`，不得因为"命中数量不足"或"缺少指标"判为不足

#### Scenario: 完全没有命中才是证据不足

- **WHEN** 本轮没有任何 `log_hit`
- **THEN** 证据状态为 `insufficient_evidence`，并标注缺失的能力是日志检索

#### Scenario: 日志检索真实失败且无命中

- **WHEN** 必需的日志检索失败（错误分类不是空结果）并且没有任何命中
- **THEN** 证据状态为 `execution_failed`

#### Scenario: 空结果不算执行失败

- **WHEN** 日志检索正常执行但返回空结果，且后续扩宽查询仍未命中
- **THEN** 证据状态为 `insufficient_evidence`，而不是 `execution_failed`

## MODIFIED Requirements

### Requirement: Planner 先获取 SOP 并发现 owner 工具

Planner SHALL 先以当前 owner scope 调用 `knowledge_retrieval` 检索 SOP，再发现当前 user enabled MCP connections 的真实工具。Planner MUST 只根据输入告警、可选 query、SOP 引用，以及本轮真实发现的只读工具的名称、描述和完整参数 schema 生成有界计划；工具集合 MUST NOT 与静态名单取交集，MUST NOT 包含已被判定为当前数据源不可用的退役工具。

Planner MUST NOT 输出任何工具参数值：计划生成时后续步骤的真实产出尚不存在，参数由 Executor 在该步骤执行时提供。没有 SOP 结果 MAY 继续，但不得伪造 SOP。当前 CLS Profile MUST 恰好包含一个 SearchLog；只要计划包含日志检索，MUST 在它之前包含恰好一个 query-builder 步骤，与该次诊断是否携带用户原始查询无关。

上下文能力由数据源决定，且不再作为计划的一部分：当前数据源的日志检索结果本身携带链路顺序，需要证明前后过程时 Planner 直接依据检索结果规划，MUST NOT 规划专门的日志上下文工具，也 MUST NOT 输出任何时序需求标志。其他步骤也 MUST 引用本轮真实发现的只读工具；模型输出不得扩大 owner、工具或权威参数权限。

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

- **WHEN** Planner 输出真实发现之外的只读工具、已被退役的工具、多个 SearchLog，或违反本轮成立的条件依赖
- **THEN** 系统在最多三次内反馈脱敏校验错误要求修正，仍无效则失败且绝不调用该计划

#### Scenario: 计划不携带参数

- **WHEN** Planner 生成任何一份可执行计划
- **THEN** 计划中的每一步只包含工具名、用途与顺序，不含任何参数值

#### Scenario: 上下文已在检索结果中

- **WHEN** 结论需要证明事件前后顺序，而日志上下文工具在当前数据源已退役
- **THEN** 计划以单次日志检索的结果作为前后过程依据，不包含上下文工具步骤，也不声明任何时序需求

### Requirement: Executor 和 Replanner 只承认真实结果

Executor SHALL 只调用本轮真实发现的只读工具，并为每次 attempt 持久化通用 tool audit、步骤状态与 checkpoint。Executor MUST 按其收到的计划逐步执行，不选择工具、不改变步骤顺序、不自行增加步骤；需要改变计划时必须交回 Replanner 处理。

Executor SHALL 在每一步执行前，依据该工具的完整参数说明、整份计划、前面步骤的真实产出与输入告警生成该步参数，并通过该工具真实 schema 的通用入参校验后才调用。成功结果 MUST 先通过工具专属输出 adapter（未登记 adapter 的工具按其产物类型规则处理），再转换为中间产物或规范化证据；失败 MUST 保存安全错误分类并产生 failed 生命周期。

**计划必须执行完毕。** 某个步骤的尝试次数耗尽时，Executor MUST 如实记录该步失败，并 MUST 把进度推进到下一步继续执行；MUST NOT 因为一步失败就把控制权提前交给 Replanner。只有计划中的每一步都被处理过（成功、失败或按规则跳过）之后，才把完整执行结果交给 Replanner。

Replanner SHALL 只做代码级验证：依据完整执行结果与已持久化证据判断是继续执行剩余步骤还是转入报告。其路由 MUST 只取决于进度与证据，MUST NOT 因为"存在失败的步骤"而提前转报告；步骤失败信息保留给报告说明使用。Replanner MUST NOT 调用模型、MUST NOT 改写计划。SearchLog 是当前 Profile 的必需运行证据；**证据充分性由真实日志命中决定，不再要求日志上下文产物作为时序结论的前提**，也不得因为缺少当前数据源无法提供的证据形态而阻止 `verified_evidence`。

#### Scenario: 工具成功产生证据

- **WHEN** SearchLog 和本轮计划使用的其他证据工具都通过真实调用与各自输出校验
- **THEN** 系统保存对应 audits、attempts、typed evidence 和稳定跨步关联，辅助 query artifact 不冒充运行证据

#### Scenario: 工具失败

- **WHEN** 计划中某个工具在有界尝试后仍失败
- **THEN** 执行结果如实记录该步失败与其类别；其余步骤继续执行；最终证据是否充分由真实日志命中决定，不得伪造任何未取得的证据

#### Scenario: 无上下文仍有充分独立证据

- **WHEN** 本轮拿到了真实日志命中，但没有日志上下文产物
- **THEN** 系统不因缺少上下文产物判定失败，证据状态由真实命中决定，并把实际使用的 evidence links 交给报告门禁

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
