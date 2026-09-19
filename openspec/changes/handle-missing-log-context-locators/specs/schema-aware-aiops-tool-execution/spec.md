## MODIFIED Requirements

### Requirement: AIOps 工具集合来自真实发现并按语义登记

系统 SHALL 以当前 owner enabled MCP connections 的本轮真实发现结果作为 AIOps 可用工具集合，MUST NOT 使用静态名单过滤。policy MUST 只承担语义登记职责：为已知工具声明能力、只读属性、依赖、产物类型，以及哪些参数由服务端注入；工具是否只读 MUST 以真实发现的 schema 与工具描述为准，具有外部写副作用的工具 MUST NOT 进入计划或被执行。

任何真实发现的只读工具 MUST 可供 Planner 规划。未登记语义的工具 MAY 被执行，其产物 MUST 按中间产物处理，MUST NOT 冒充运行证据。Planner MUST 获得允许工具的名称、描述与完整参数 schema，而不是被裁剪过的摘要或仅名称。

**工具可用性 MUST 同时反映数据源能否满足其前置条件。** 当某个工具的必填参数在当前数据源上不可能被满足（例如日志来源永远产不出该工具要求的定位字段）时，系统 MUST 在当前数据源下**退役**该工具：它 MUST NOT 出现在 Planner 可见的工具目录中、MUST NOT 进入 registry、也 MUST NOT 被调用。退役判定 MUST 有明确依据，MUST NOT 用"未登记语义"代替。

#### Scenario: 官方 Server 返回额外工具

- **WHEN** MCP Server 真实发现 SearchLog、告警管理、主题管理、时间换算和其他只读工具
- **THEN** Planner 收到全部发现的只读工具及其名称、描述与完整参数 schema，未被显式登记的工具同样可被规划

#### Scenario: 运行中工具集变化

- **WHEN** durable job 恢复时原计划工具不再属于当前 owner 的真实发现白名单
- **THEN** 系统拒绝调用并以安全工具不可用错误失败，不使用历史工具句柄绕过真实发现结果

#### Scenario: 模型可见说明不含服务端权威字段

- **WHEN** 一个工具的某些参数由服务端确定性注入
- **THEN** 这些字段 MUST NOT 出现在模型可见的参数说明与必填列表中

#### Scenario: 只读辅助工具可被规划

- **WHEN** 计划需要先取得当前时间才能构造合法时间范围，且本轮真实发现并登记了时间戳转换类只读工具
- **THEN** 该工具可以进入计划并被调用，其产出作为中间产物供后续步骤与 Replanner 使用，但不计入证据充分性判断

#### Scenario: 写副作用工具仍被拒绝

- **WHEN** 某个已发现工具具有外部写副作用
- **THEN** 它不进入可用工具集合，也不出现在 Planner 可见的工具目录与计划中

#### Scenario: 前置条件无法满足的工具被退役

- **WHEN** 某个只读工具的必填参数只能来自当前数据源产不出的字段
- **THEN** 该工具不出现在 Planner 可见目录、不进入 registry、也不可被调用；系统在文档中记录该退役结论与判定依据

#### Scenario: 退役工具与语义未登记的工具区分开

- **WHEN** 一个工具既没有语义登记，也没有被判定为数据源不可用
- **THEN** 它仍按"未登记语义"处理（可执行、产物落中间产物），MUST NOT 被当作退役工具隐藏

### Requirement: Planner 按条件能力依赖而非固定三工具生成计划

Planner SHALL 获得本轮真实发现的只读工具的名称、描述与完整参数 schema，而不是被裁剪过的摘要或仅名称。Planner SHALL 只生成诊断流程本身：每一步包含工具名、用途与调用顺序，MUST NOT 生成任何工具参数值，因为计划生成时后续步骤的真实产出尚不存在，参数由执行者在该步骤真正执行时提供。

当前 CLS 诊断 Profile MUST 恰好包含一个真实 SearchLog。只要计划包含日志检索步骤，MUST 在它之前包含且仅包含一个已登记的 query-builder 步骤，与该次诊断是否携带用户原始查询无关。

**上下文能力按数据源可用性决定。** 当上下文工具在当前数据源上可用时，只有计划结论需要事件前后文且 SearchLog 原始命中提供定位字段，它才成为该结论的必需依赖；当该工具已被退役时（当前数据源产不出它要求的定位字段），计划 MUST NOT 包含它，`requiresTemporalContext` MUST NOT 被要求对应一个上下文步骤——否则模型一旦声明时序需求，其计划将永远无法通过校验。Planner 的可读说明 MUST 表达"当前链路的日志检索结果本身已包含链路顺序信息"，使它能据此规划单次检索而不是寻找另一个上下文工具。

knowledge retrieval 保持 owner scope；其他只读工具只有真实发现时才可加入。工具名匹配 MUST 与语义登记表的匹配规则一致。Planner MUST 在最多三次内获得脱敏校验错误以修正计划；仍无效则失败且绝不调用该计划。

#### Scenario: 未验证 Query 需要 query-builder

- **WHEN** 计划包含一个 SearchLog 步骤
- **THEN** 计划在该 SearchLog 之前生成并验证 CQL，无论本次诊断是否携带用户原始查询

#### Scenario: 服务端已有可信 Query

- **WHEN** 服务端已根据受信任 incident/trace 条件拼出一段候选查询
- **THEN** 该候选只作为 query-builder 的输入参考，计划仍然 MUST 包含一个 query-builder 步骤，不直接执行 SearchLog

#### Scenario: 结论需要日志上下文

- **WHEN** 上下文工具在当前数据源可用，且 Planner 要证明调用顺序、重试、熔断或恢复等时序结论，同时 SearchLog 命中具有上下文定位字段
- **THEN** 该工具必须位于对应 SearchLog 之后，其结果进入对应 claim 的证据充分性判断

#### Scenario: 计划违反条件依赖

- **WHEN** 模型生成多个 SearchLog、把上下文工具放在 SearchLog 前，或引用真实发现之外的只读工具
- **THEN** 计划在持久化和调用前被拒绝，并进入有界计划纠错

#### Scenario: 计划不携带参数

- **WHEN** Planner 生成任何一份可执行计划
- **THEN** 计划中的每一步只包含工具名、用途与顺序，不含任何参数值

#### Scenario: 工具名大小写或分隔符不一致

- **WHEN** Planner 输出的工具名在大小写或分隔符上与真实发现名称不同，但按登记表的宽松匹配规则等价
- **THEN** 计划校验接受该工具名，而不是以"引用未注册工具"拒绝

#### Scenario: 模型看到的工具参数说明

- **WHEN** 系统把可用工具交给 Planner 或执行者的填参调用
- **THEN** 每个字段都携带官方 schema 提供的用途说明与约束（类型、枚举、格式、默认值），必填项与官方一致；`Region`、`TopicId` 等由服务端注入的字段不出现在该说明与必填列表中

#### Scenario: 上下文工具已退役时计划仍然合法

- **WHEN** 上下文工具因数据源不满足前置条件而退役，计划却声明了时序需求
- **THEN** 计划校验不要求存在上下文步骤，计划可以正常通过；Planner 的可读说明已经告知上下文信息包含在日志检索结果中

#### Scenario: 退役的上下文工具不可被规划

- **WHEN** Planner 试图规划已被退役的上下文工具
- **THEN** 该工具名不在可用工具目录中，计划被拒绝并进入有界纠错
