## Purpose

本能力把真实 MCP 动态发现收敛为可验证、可恢复的 AIOps 工具执行边界，使 Planner 只能规划经过能力登记的只读工具，并依据查询来源、结论需要和实际命中条件选择 CLS 能力，而不是把固定工具数量当成可靠性的替代品。

## ADDED Requirements

### Requirement: AIOps 工具集合使用双层白名单
系统 SHALL 保留当前 owner enabled MCP connections 的本轮真实发现结果作为安全白名单，并仅把其中与 AIOps evidence-tool policy 相交的工具交给 Planner。policy MUST 明确工具能力、只读属性、依赖、输入验证器、输出 adapter、产物类型和重试策略；未发现、未登记、具有外部写副作用、缺少输入验证器，或产物无法被安全解释的工具 MUST NOT 进入计划。

#### Scenario: 官方 Server 返回额外工具
- **WHEN** MCP Server 真实发现 SearchLog、告警管理、主题管理和其他工具，但 policy 只登记只读取证能力
- **THEN** Planner 只收到发现结果与 policy 的交集，其他工具保持不可规划且不会被调用

#### Scenario: 运行中工具集变化
- **WHEN** durable job 恢复时原计划工具不再属于当前 owner 的真实发现白名单或 policy
- **THEN** 系统拒绝调用并以安全工具不可用错误失败，不使用历史工具句柄绕过白名单

### Requirement: Planner 按条件能力依赖而非固定三工具生成计划
Planner SHALL 获得允许工具的名称、用途、输入 Schema 摘要、能力、依赖关系与安全限制，而不是仅获得名称。当前 CLS 诊断 Profile MUST 恰好包含一个真实 SearchLog；Query 尚未由服务端可信生成或校验时 MUST 在 SearchLog 前使用已登记 query-builder，已有可信 Query 时 MUST NOT 为凑步骤重复生成。只有计划结论需要事件前后文且 SearchLog 原始命中提供 Time/PkgId/PkgLogId 时，DescribeLogContext 才成为该结论的必需依赖。knowledge retrieval 保持 owner scope，可选 metric 或其他证据工具只有真实发现且通过 policy 时才可加入。

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

### Requirement: 所有允许工具校验输入且所有产物显式适配
每个进入 AIOps policy 的工具 SHALL 在调用前根据 runtime args schema 与本地语义约束校验并规范化输入。证据型工具 MUST 有显式输出 adapter 和 evidence kind；query-builder 等辅助工具 MUST 有中间产物 adapter。核心 `TextToSearchLogQuery`、`SearchLog`、`DescribeLogContext` SHALL 使用显式 Pydantic 输入、输出和中间结果模型。调用后 MUST 解包真实 MCP content/structured content 并验证工具专属输出；工具返回成功文本但不满足输出合同 MUST 视为失败，禁止保存为成功证据。

#### Scenario: SearchLog 返回有效原始日志
- **WHEN** SearchLog 返回含 Time、非空 PkgId、合法 PkgLogId 和 LogJson 的原始日志项
- **THEN** 系统保存 typed log-hit 证据，并允许选择命中项继续上下文查询

#### Scenario: 工具返回无法解析内容
- **WHEN** MCP 返回错误 wrapper、非 JSON 内容、缺失必填字段或类型错误
- **THEN** 系统记录输出校验错误和 failed attempt，不把字符串摘要冒充结构化证据

#### Scenario: 其他白名单证据工具
- **WHEN** QueryMetric 或未来工具已真实发现并登记为 AIOps 证据能力
- **THEN** 它必须通过自己的输入验证器和输出 adapter 后才能进入 Planner 和 evidence，不能复用 CLS 日志模型强行解析

### Requirement: CLS 权威参数由服务端确定性传递
当前运行时 SHALL 继续从 ignored 本地 JSON 深合并后的 `clsLogUpload.region` 与 `clsLogUpload.topicId` 取得可信默认值，不新增远端日志源发现或路由。SearchLog 的时间范围和 query MUST 经过有界规范化；DescribeLogContext 的 Region/TopicId MUST 使用相同本地默认值，Time/PkgId/PkgLogId MUST 来自本轮已验证的 SearchLog 命中，模型和客户端不得覆盖这些字段。

#### Scenario: 上下文参数装配
- **WHEN** SearchLog 产生一个有效命中且 Planner 进入 DescribeLogContext
- **THEN** 系统从本地配置注入 Region/TopicId，从该命中注入 Time/PkgId/PkgLogId，再校验后调用工具

#### Scenario: 本地默认值缺失
- **WHEN** 计划需要 SearchLog 或 DescribeLogContext，但 `clsLogUpload.region` 或 `clsLogUpload.topicId` 为空
- **THEN** 诊断在调用该 CLS 工具前以明确配置错误失败，不让模型猜测或从日志正文反推

### Requirement: 工具纠错与重试有界且可审计
每个计划步骤 SHALL 最多执行三次 attempt。Pydantic validation 只负责产生结构化字段错误，独立错误策略 MUST 决定 retry、replan 或 permanent failure。可修正输入错误 MAY 将脱敏字段错误和允许 Schema 交给模型修正非权威参数；空结果 MAY 由 Replanner 调整查询；timeout、429 和临时 5xx SHALL 有界退避；配置缺失、401/403、owner 越权、工具未允许、runtime Schema 不兼容和其他永久 4xx MUST NOT 重试。Region、TopicId 以及已验证的跨步参数不得由纠错模型修改。每次 attempt MUST 写入 owner-scoped step、tool audit、持久事件和 checkpoint。

#### Scenario: 第二次修正成功
- **WHEN** 首次参数校验失败，模型依据脱敏错误修正 Query 或可选范围且第二次通过
- **THEN** 系统记录一次 failed attempt 和一次 succeeded attempt，并只把真实成功输出保存为证据

#### Scenario: 三次仍失败
- **WHEN** 同一步达到三次上限仍未通过校验或真实调用
- **THEN** 步骤明确失败，Replanner 只能选择其他已登记真实证据；最终证据仍不足时不得进入可信报告或案例沉淀

#### Scenario: 永久错误不重试
- **WHEN** 工具失败原因是本地配置缺失、授权拒绝、owner 越权或 Schema 版本不兼容
- **THEN** 系统只记录一次 failed attempt 并立即进入安全失败处理，不把错误交给模型猜测修复

### Requirement: 工具结果按显式证据类型持久化
系统 SHALL 使用 adapter 声明的产物类型映射结果，至少区分 query artifact、log hit、log context、metric 和 knowledge；不得继续把工具名称的字符串包含关系作为核心证据类型判断。辅助产物只用于确定性组装后续参数，不冒充运行证据。日志、审计和 SSE 只暴露安全摘要、参数键、状态、分类和耗时，不输出凭据、完整参数值或原始 MCP JSON。

#### Scenario: DescribeLogContext 形成上下文证据
- **WHEN** DescribeLogContext 返回通过校验的前后日志
- **THEN** 系统保存可追溯的 log-context 证据并关联 SearchLog 命中、step 和 tool call

#### Scenario: 未登记输出类型
- **WHEN** 一个真实发现工具没有输出 adapter 或安全产物类型
- **THEN** 它不会进入 Planner，且不能通过通用字符串序列化绕过证据边界
