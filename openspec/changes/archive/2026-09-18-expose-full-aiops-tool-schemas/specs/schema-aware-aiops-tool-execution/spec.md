## MODIFIED Requirements

### Requirement: AIOps 工具集合使用双层白名单
系统 SHALL 保留当前 owner enabled MCP connections 的本轮真实发现结果作为安全白名单，并仅把其中与 AIOps evidence-tool policy 相交的工具交给 Planner。policy MUST 明确工具能力、只读属性、依赖、输入验证器、输出 adapter、产物类型和重试策略；未发现、未登记、具有外部写副作用、缺少输入验证器，或产物无法被安全解释的工具 MUST NOT 进入计划。policy SHALL 区分两类只读工具：**证据型工具**产出诊断证据并参与证据充分性判断；**只读辅助型工具**（例如时间戳转换、日志主题索引查询）允许规划与调用，其产出作为中间产物进入模型可见上下文，但 MUST NOT 计入证据充分性判断。官方 server 已真实发现且通过只读判定的辅助工具 MUST 可以进入计划，不得因为"不产出证据"而一律排除。

#### Scenario: 官方 Server 返回额外工具
- **WHEN** MCP Server 真实发现 SearchLog、告警管理、主题管理和其他工具，但 policy 只登记只读取证能力
- **THEN** Planner 只收到发现结果与 policy 的交集，其他工具保持不可规划且不会被调用

#### Scenario: 运行中工具集变化
- **WHEN** durable job 恢复时原计划工具不再属于当前 owner 的真实发现白名单或 policy
- **THEN** 系统拒绝调用并以安全工具不可用错误失败，不使用历史工具句柄绕过白名单

#### Scenario: 只读辅助工具可被规划
- **WHEN** 计划需要先取得当前时间才能构造合法时间范围，且本轮真实发现并登记了时间戳转换类只读工具
- **THEN** 该工具可以进入计划并被调用，其产出作为中间产物供后续步骤与 Replanner 使用，但不计入证据充分性判断

#### Scenario: 写副作用工具仍被拒绝
- **WHEN** 某个已发现工具具有外部写副作用
- **THEN** 它不进入 policy，也不出现在 Planner 可见的工具目录与计划中

### Requirement: Planner 按条件能力依赖而非固定三工具生成计划
Planner SHALL 获得允许工具的完整输入参数说明：字段名、类型、字段用途、取值范围或枚举、格式、默认值与必填项，而不是仅获得名称，也不是被裁剪成"只有类型"的摘要。唯一例外是服务端权威字段：`Region`、`TopicId` 等由服务端注入的字段 MUST 从模型可见的参数说明与必填列表中移除。当前 CLS 诊断 Profile MUST 恰好包含一个真实 SearchLog；Query 尚未由服务端可信生成或校验时 MUST 在 SearchLog 前使用已登记 query-builder，已有可信 Query 时 MUST NOT 为凑步骤重复生成。只有计划结论需要事件前后文且 SearchLog 原始命中提供 Time/PkgId/PkgLogId 时，DescribeLogContext 才成为该结论的必需依赖。knowledge retrieval 保持 owner scope，可选 metric 或其他证据工具只有真实发现且通过 policy 时才可加入。

#### Scenario: 未验证 Query 需要 query-builder
- **WHEN** 诊断只有自然语言意图且本轮真实发现并允许 TextToSearchLogQuery
- **THEN** 有效计划先生成并验证 CQL，再执行唯一 SearchLog

#### Scenario: 服务端已有可信 Query
- **WHEN** 服务端已根据受信任 incident/trace 条件生成并校验 SearchLog Query
- **THEN** 计划可以直接执行唯一 SearchLog，不强制调用 TextToSearchLogQuery

#### Scenario: 结论需要日志上下文
- **WHEN** Planner 要证明调用顺序、重试、熔断或恢复等时序结论，且 SearchLog 命中具有上下文定位字段
- **THEN** DescribeLogContext 必须位于该 SearchLog 之后，其结果进入对应 claim 的证据充分性判断

#### Scenario: 计划违反条件依赖
- **WHEN** 模型生成多个 SearchLog、把 DescribeLogContext 放在 SearchLog 前、在缺少定位字段时伪造上下文参数，或引用未允许工具
- **THEN** 计划在持久化和调用前被拒绝，并进入有界计划纠错

#### Scenario: 模型看到的工具参数说明
- **WHEN** 系统把允许工具交给 Planner 或 Replanner
- **THEN** 每个字段都携带官方 schema 提供的用途说明与约束（类型、枚举、格式、默认值），必填项与官方一致；`Region`、`TopicId` 等由服务端注入的字段不出现在该说明与必填列表中

### Requirement: 所有允许工具校验输入且所有产物显式适配
每个进入 AIOps policy 的工具 SHALL 在调用前根据 runtime args schema 与本地语义约束校验并规范化输入。证据型工具 MUST 有显式输出 adapter 和 evidence kind；query-builder 等辅助工具 MUST 有中间产物 adapter。核心 `TextToSearchLogQuery`、`SearchLog`、`DescribeLogContext` SHALL 使用显式 Pydantic 输入、输出和中间结果模型。调用后 MUST 解包真实 MCP content/structured content 并验证工具专属输出；工具返回成功文本但不满足输出合同 MUST 视为失败，禁止保存为成功证据。query-builder 的中间产物 adapter 在提取生成结果后 MUST 还原文本转义，使产出的查询可直接执行；MUST NOT 把 `\n`、`\"` 等转义序列作为字面量传给下游工具。调用前的规范化 MUST 只做两件事：注入服务端权威字段、按官方 schema 校验；MUST NOT 用别名映射、默认时间窗、默认查询、单位换算或时间窗重置去补偿模型输入。

#### Scenario: SearchLog 返回有效原始日志
- **WHEN** SearchLog 返回含 Time、非空 PkgId、合法 PkgLogId 和 LogJson 的原始日志项
- **THEN** 系统保存 typed log-hit 证据，并允许选择命中项继续上下文查询

#### Scenario: 工具返回无法解析内容
- **WHEN** MCP 返回错误 wrapper、非 JSON 内容、缺失必填字段或类型错误
- **THEN** 系统记录输出校验错误和 failed attempt，不把字符串摘要冒充结构化证据

#### Scenario: 其他白名单证据工具
- **WHEN** QueryMetric 或未来工具已真实发现并登记为 AIOps 证据能力
- **THEN** 它必须通过自己的输入验证器和输出 adapter 后才能进入 Planner 和 evidence，不能复用 CLS 日志模型强行解析

#### Scenario: 生成的查询含转义序列
- **WHEN** query-builder 的返回把生成的 CQL 嵌在转义文本里（例如围栏代码块里带 `\n` 与 `\"`）
- **THEN** 中间产物 adapter 还原转义后再产出查询，交给 SearchLog 的 Query 不含字面量转义序列

#### Scenario: 模型参数不合规
- **WHEN** 模型给出的参数缺少必填项、类型不符、时间单位错误或字段名不在官方 schema 中
- **THEN** 系统直接以校验错误失败并把错误与完整参数说明交回模型修正，不静默补齐默认值、不改写字段名、不换算单位

### Requirement: CLS 权威参数由服务端确定性传递
当前运行时 SHALL 继续从 ignored 本地 JSON 深合并后的 `clsLogUpload.region` 与 `clsLogUpload.topicId` 取得可信默认值，不新增远端日志源发现或路由。SearchLog 的 `Region`、`TopicId` MUST 由服务端注入且模型不得提供或覆盖；其余参数（时间范围、Query、Limit 等）MUST 来自模型或已验证的中间产物，系统 MUST NOT 为其提供默认值或做单位换算。DescribeLogContext 的 Region/TopicId MUST 使用相同本地默认值，Time/PkgId/PkgLogId MUST 来自本轮已验证的 SearchLog 命中，模型和客户端不得覆盖这些字段。

#### Scenario: 上下文参数装配
- **WHEN** SearchLog 产生一个有效命中且 Planner 进入 DescribeLogContext
- **THEN** 系统从本地配置注入 Region/TopicId，从该命中注入 Time/PkgId/PkgLogId，再校验后调用工具

#### Scenario: 模型提供了服务端权威字段
- **WHEN** 模型在计划参数里给出 `Region` 或 `TopicId`
- **THEN** 系统忽略该取值并以本地配置注入值为准，且这两个字段不出现在模型可见的参数说明中

#### Scenario: 本地默认值缺失
- **WHEN** 计划需要 SearchLog 或 DescribeLogContext，但 `clsLogUpload.region` 或 `clsLogUpload.topicId` 为空
- **THEN** 诊断在调用该 CLS 工具前以明确配置错误失败，不让模型猜测或从日志正文反推
