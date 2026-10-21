# Spec Delta

## MODIFIED Requirements

### Requirement: Planner 先获取 SOP 并发现 owner 工具

Planner SHALL 先以当前 owner scope 调用 `knowledge_retrieval` 检索 SOP，再发现当前 user enabled MCP connections 的真实工具。Planner MUST 只根据输入告警、可选 query、SOP 引用，以及本轮真实发现的只读工具的名称、描述和完整参数 schema 生成有界计划；工具集合 MUST NOT 与静态名单取交集，MUST NOT 包含已被判定为当前数据源不可用的退役工具。

当本轮存在非空 query 时，Planner MUST 在独立的 `用户问题` 输入中直接获得该 query，MUST NOT 要求它从 SOP、告警或工具结果反推用户目标。有 query 时，query SHALL 定义诊断目标，告警 SHALL 提供对象、时间与上下文，SOP SHALL 只提供辅助经验；SOP 与 query 不一致时 MUST NOT 用 SOP 替代 query。没有 query 且有告警时，Planner SHALL 以告警定义诊断目标。query 与告警同时存在时，两者均 MUST 可见。

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

#### Scenario: 纯 query 且没有 SOP

- **WHEN** 本轮 query 非空、alerts 为空且 knowledge retrieval 没有返回 SOP
- **THEN** Planner 仍收到原始 query，并围绕该 query 生成有界计划，不把“没有 SOP”解释为“没有诊断目标”

#### Scenario: query 与 SOP 不一致

- **WHEN** query 描述的问题与检索到的 SOP 不是同一类故障
- **THEN** Planner 以 query 为诊断目标，只把 SOP 当作可能相关的辅助资料，不擅自改为诊断 SOP 中的另一种故障

#### Scenario: 只有告警没有 query

- **WHEN** 本轮 query 为空但存在一条或多条有效告警
- **THEN** Planner 以告警内容生成计划，且不要求或伪造用户 query

#### Scenario: query 与告警同时存在

- **WHEN** 本轮同时提供非空 query 和有效告警
- **THEN** Planner 同时获得两者，并以 query 说明用户关注点、以告警补充对象、时间与上下文
