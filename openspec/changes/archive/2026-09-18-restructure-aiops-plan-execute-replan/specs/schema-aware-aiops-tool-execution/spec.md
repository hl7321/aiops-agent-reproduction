## MODIFIED Requirements

### Requirement: AIOps 工具集合来自真实发现并按语义登记

系统 SHALL 以当前 owner enabled MCP connections 的本轮真实发现结果作为 AIOps 可用工具集合，MUST NOT 使用静态名单过滤。policy MUST 只承担语义登记职责：为已知工具声明能力、只读属性、依赖、产物类型，以及哪些参数由服务端注入；工具是否只读 MUST 以真实发现的 schema 与工具描述为准，具有外部写副作用的工具 MUST NOT 进入计划或被执行。

任何真实发现的只读工具 MUST 可供 Planner 规划。未登记语义的工具 MAY 被执行，其产物 MUST 按中间产物处理，MUST NOT 冒充运行证据。Planner MUST 获得允许工具的名称、描述与完整参数 schema，而不是被裁剪过的摘要或仅名称。

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

### Requirement: Planner 按条件能力依赖而非固定三工具生成计划

Planner SHALL 获得本轮真实发现的只读工具的名称、描述与完整参数 schema，而不是被裁剪过的摘要或仅名称。Planner SHALL 只生成诊断流程本身：每一步包含工具名、用途与调用顺序，MUST NOT 生成任何工具参数值，因为计划生成时后续步骤的真实产出尚不存在，参数由执行者在该步骤真正执行时提供。

当前 CLS 诊断 Profile MUST 恰好包含一个真实 SearchLog。只要计划包含日志检索步骤，MUST 在它之前包含且仅包含一个已登记的 query-builder 步骤，与该次诊断是否携带用户原始查询无关。只有计划结论需要事件前后文且 SearchLog 原始命中提供 Time/PkgId/PkgLogId 时，DescribeLogContext 才成为该结论的必需依赖。knowledge retrieval 保持 owner scope；其他只读工具只有真实发现时才可加入。

工具名匹配 MUST 与语义登记表的匹配规则一致，不得出现"登记表认可但计划校验拒绝"的两套标准。Planner MUST 在最多三次内获得脱敏校验错误以修正计划；仍无效则失败且绝不调用该计划。

#### Scenario: 未验证 Query 需要 query-builder

- **WHEN** 计划包含一个 SearchLog 步骤
- **THEN** 计划在该 SearchLog 之前生成并验证 CQL，无论本次诊断是否携带用户原始查询

#### Scenario: 服务端已有可信 Query

- **WHEN** 服务端已根据受信任 incident/trace 条件拼出一段候选查询
- **THEN** 该候选只作为 query-builder 的输入参考，计划仍然 MUST 包含一个 query-builder 步骤，不直接执行 SearchLog

#### Scenario: 结论需要日志上下文

- **WHEN** Planner 要证明调用顺序、重试、熔断或恢复等时序结论，且 SearchLog 命中具有上下文定位字段
- **THEN** DescribeLogContext 必须位于该 SearchLog 之后，其结果进入对应 claim 的证据充分性判断

#### Scenario: 计划违反条件依赖

- **WHEN** 模型生成多个 SearchLog、把 DescribeLogContext 放在 SearchLog 前、在缺少定位字段时伪造上下文参数，或引用真实发现之外的只读工具
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

### Requirement: 所有允许工具校验输入且所有产物显式适配

每个可执行工具 SHALL 在调用前按其真实 runtime schema 做通用入参校验，至少覆盖：必填字段齐全、拒绝 schema 未声明的键、值类型匹配、声明了取值范围或枚举时取值合法。该通用校验 MUST 对被规划的全部工具生效，MUST NOT 只覆盖少数核心工具。核心 `TextToSearchLogQuery`、`SearchLog`、`DescribeLogContext` MAY 在此之上继续使用显式 Pydantic 输入模型与语义规范化。

证据型工具 MUST 有显式输出 adapter 和 evidence kind；query-builder 等辅助工具 MUST 有中间产物 adapter。调用后 MUST 解包真实 MCP content/structured content 并验证工具专属输出；工具返回成功文本但不满足输出合同 MUST 视为失败，禁止保存为成功证据。未登记输出 adapter 的只读工具，其产物 MUST 统一按中间产物持久化，MUST NOT 进入证据充分性判断。query-builder 的中间产物 adapter 在提取生成结果后 MUST 还原文本转义，使产出的查询可直接执行；MUST NOT 把 `\n`、`\"` 等转义序列作为字面量传给下游工具。

#### Scenario: SearchLog 返回有效原始日志

- **WHEN** SearchLog 返回含 Time、非空 PkgId、合法 PkgLogId 和 LogJson 的原始日志项
- **THEN** 系统保存 typed log-hit 证据，并允许选择命中项继续上下文查询

#### Scenario: 工具返回无法解析内容

- **WHEN** MCP 返回错误 wrapper、非 JSON 内容、缺失必填字段或类型错误
- **THEN** 系统记录输出校验错误和 failed attempt，不把字符串摘要冒充结构化证据

#### Scenario: 其他白名单证据工具

- **WHEN** QueryMetric 或其他已登记证据能力的工具被真实发现并执行
- **THEN** 它必须通过自己的输出 adapter 后才能进入 evidence，不能复用 CLS 日志模型强行解析

#### Scenario: 生成的查询含转义序列

- **WHEN** query-builder 的返回把生成的 CQL 嵌在转义文本中（例如围栏代码块里带 `\n` 与 `\"`）
- **THEN** 中间产物 adapter 还原转义后再产出查询，交给 SearchLog 的 Query 不含字面量转义序列

#### Scenario: 入参缺少必填字段或含未声明键

- **WHEN** 某一步生成的参数缺少该工具 schema 声明的必填字段，或包含 schema 未声明的键
- **THEN** 系统在调用前以结构化字段错误拒绝该次尝试，不发出真实工具调用

#### Scenario: 未被显式登记的工具被调用

- **WHEN** 计划使用一个真实发现但未登记输出 adapter 的只读工具并成功返回
- **THEN** 系统把该产物按中间产物持久化，它可被后续步骤与重规划使用，但不计入证据充分性判断

#### Scenario: 模型参数不合规

- **WHEN** 模型给出的参数缺少必填项、类型不符、时间单位错误或字段名不在官方 schema 中
- **THEN** 系统直接以校验错误失败并把错误与完整参数说明交回模型修正，不静默补齐默认值、不改写字段名、不换算单位

### Requirement: CLS 权威参数由服务端确定性传递

当前运行时 SHALL 继续从 ignored 本地 JSON 深合并后的 `clsLogUpload.region` 与 `clsLogUpload.topicId` 取得可信默认值，不新增远端日志源发现或路由。Region 与 TopicId MUST 由服务端无条件注入，模型和客户端 MUST NOT 覆盖，且 MUST NOT 出现在模型可见的参数说明中。

依赖前面步骤真实产出的字段 SHALL 由执行者在执行该步骤时提供，MUST NOT 在计划阶段预先写死。执行者 MUST 按字段性质区分来源：

- **计划保证的跨步配对**（SearchLog 的 Query 来自其必需的 query-builder 步骤产出、DescribeLogContext 的 Time/PkgId/PkgLogId 来自本轮已验证的 SearchLog 命中）MUST 由执行者**确定性绑定**，MUST NOT 交给模型生成，也 MUST NOT 出现在模型可见的参数说明中——这些是"搬运"而不是"判断"，交给模型只会让计划校验要求的步骤失去意义。
- **其余需要判断的字段**（时间窗、返回条数、自然语言检索意图、其他工具自有的参数）SHALL 由执行者依据当前工具说明与前序产出生成。

无论来源如何，最终参数 MUST 通过该工具的真实 schema 校验后才可调用。

#### Scenario: 上下文参数装配

- **WHEN** SearchLog 产生一个有效命中且计划进入 DescribeLogContext
- **THEN** 系统从本地配置注入 Region/TopicId，执行者从该命中产出填入 Time/PkgId/PkgLogId，再经 schema 校验后才调用工具

#### Scenario: 本地默认值缺失

- **WHEN** 计划需要 SearchLog 或 DescribeLogContext，但 `clsLogUpload.region` 或 `clsLogUpload.topicId` 为空
- **THEN** 诊断在调用该 CLS 工具前以明确配置错误失败，不让模型猜测或从日志正文反推

#### Scenario: 模型提供了服务端权威字段

- **WHEN** 模型在执行参数里给出 `Region` 或 `TopicId`
- **THEN** 系统忽略该取值并以本地配置注入值为准，且这两个字段不出现在模型可见的参数说明中

#### Scenario: 跨步骤参数由执行者填写

- **WHEN** 执行者执行一个需要前面步骤产出的步骤
- **THEN** 属于计划保证配对的字段被确定性绑定、其余字段由模型依据前序产出生成，全部通过该工具真实 schema 校验后才执行

#### Scenario: 绑定字段不接受模型取值

- **WHEN** 模型为已由执行者绑定的字段（例如 SearchLog 的 Query）给出别的取值
- **THEN** 执行者以绑定值为准，模型取值被忽略，且该字段不出现在模型可见的参数说明中

### Requirement: 工具纠错与重试有界且可审计

每个计划步骤 SHALL 最多执行两次 attempt。错误策略 MUST 把失败分为三类，并把分类结果写入该步骤的执行结果：

1. **原样重试**：超时、限流、临时服务端错误、连接中断，SHALL 有界退避后原样重试。
2. **修正后重试**：入参校验失败，SHALL 把脱敏字段错误与该工具的完整参数说明交回模型修正后重试。
3. **不可重试**：本地配置缺失、授权拒绝、owner 越权、runtime Schema 不兼容、输出无法翻译，MUST 立即停止该步骤的重试，MUST NOT 把错误交给模型猜测修复。

错误分类 MUST 识别外部服务以执行错误形式返回的参数校验失败，MUST NOT 把入参错误归类为可重试的传输错误。Region、TopicId 以及已验证的跨步参数不得由纠错模型修改。每次 attempt MUST 写入 owner-scoped step、tool audit、持久事件和 checkpoint。失败分类 MUST 在脱敏前提下保留一段有界长度的服务端消息摘要，使失败原因可从 step、tool audit 与持久事件中读出；该摘要 MUST NOT 包含凭据、Region、TopicId 或其他敏感参数值。

#### Scenario: 第二次修正成功

- **WHEN** 首次参数校验失败，模型依据脱敏错误修正 Query 或可选范围且第二次通过
- **THEN** 系统记录一次 failed attempt 和一次 succeeded attempt，并只把真实成功输出保存为证据

#### Scenario: 三次仍失败

- **WHEN** 同一步连续尝试达到本变更定义的上限（两次）仍未通过校验或真实调用
- **THEN** 步骤明确失败，执行结果记录尝试次数、每次失败原因与是否可重试，后续按真实证据进入报告或安全失败

#### Scenario: 永久错误不重试

- **WHEN** 工具失败原因是本地配置缺失、授权拒绝、owner 越权、Schema 版本不兼容或输出无法翻译
- **THEN** 系统只记录一次 failed attempt，把"不可重试"与错误类型写入执行结果，不进行第二次调用

#### Scenario: 服务端返回可读错误

- **WHEN** 外部日志服务以执行错误形式返回语法错误、字段不存在或权限不足
- **THEN** step、tool audit 与持久事件中可见该错误的脱敏摘要，且不出现凭据、Region、TopicId 的具体值

#### Scenario: 入参错误被正确分类

- **WHEN** 外部服务以执行错误形式返回必填字段缺失或参数校验失败
- **THEN** 该失败被归类为入参错误并进入修正流程，而不是被当作可重试的传输错误重复原样调用

### Requirement: 工具结果按显式证据类型持久化

系统 SHALL 使用 adapter 声明的产物类型映射结果，至少区分 query artifact、log hit、log context、metric 和 knowledge；不得继续把工具名称的字符串包含关系作为核心证据类型判断。辅助产物只用于确定性组装后续参数，不冒充运行证据。未登记输出 adapter 的真实发现工具，其产物 MUST 统一按中间产物持久化，不得进入证据充分性判断。日志、审计和 SSE 只暴露安全摘要、参数键、状态、分类和耗时，不输出凭据、完整参数值或原始 MCP JSON。

#### Scenario: DescribeLogContext 形成上下文证据

- **WHEN** DescribeLogContext 返回通过校验的前后日志
- **THEN** 系统保存可追溯的 log-context 证据并关联 SearchLog 命中、step 和 tool call

#### Scenario: 未登记输出类型

- **WHEN** 一个真实发现的只读工具没有登记输出 adapter
- **THEN** 它的产物按中间产物持久化且不计入证据充分性判断，不通过通用字符串序列化绕过证据边界，也不因此被排除在计划之外
