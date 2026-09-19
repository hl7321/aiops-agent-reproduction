## MODIFIED Requirements

### Requirement: Planner 先获取 SOP 并发现 owner 工具

Planner SHALL 先以当前 owner scope 调用 `knowledge_retrieval` 检索 SOP，再发现当前 user enabled MCP connections 的真实工具。Planner MUST 只根据输入告警、可选 query、SOP 引用，以及本轮真实发现的只读工具的名称、描述和完整参数 schema 生成有界计划；工具集合 MUST NOT 再与静态名单取交集，MUST NOT 包含已被判定为当前数据源不可用的退役工具。

Planner MUST NOT 输出任何工具参数值：计划生成时后续步骤的真实产出尚不存在，参数由 Executor 在该步骤执行时提供。没有 SOP 结果 MAY 继续，但不得伪造 SOP。当前 CLS Profile MUST 恰好包含一个 SearchLog；只要计划包含日志检索，MUST 在它之前包含恰好一个 query-builder 步骤，与该次诊断是否携带用户原始查询无关。

上下文能力按数据源可用性决定：当上下文工具在当前数据源可用且命中提供定位字段时，它才可能成为结论的必需依赖；当该工具已退役时，计划 MUST NOT 包含它，声明时序需求也 MUST NOT 被要求对应一个上下文步骤，且 Planner 的可读说明 MUST 表达"日志检索结果本身已包含链路顺序信息"。其他步骤也 MUST 引用本轮真实发现的只读工具；模型输出不得扩大 owner、工具或权威参数权限。

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

- **WHEN** 上下文工具已退役，且本轮日志检索返回同一链路的连续多行日志
- **THEN** 计划以单次检索满足对前后过程的取证需要，不因为缺少上下文工具而拒绝生成计划
