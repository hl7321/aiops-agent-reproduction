## MODIFIED Requirements

### Requirement: 所有允许工具校验输入且所有产物显式适配
每个进入 AIOps policy 的工具 SHALL 在调用前根据 runtime args schema 与本地语义约束校验并规范化输入。证据型工具 MUST 有显式输出 adapter 和 evidence kind；query-builder 等辅助工具 MUST 有中间产物 adapter。核心 `TextToSearchLogQuery`、`SearchLog`、`DescribeLogContext` SHALL 使用显式 Pydantic 输入、输出和中间结果模型。调用后 MUST 解包真实 MCP content/structured content 并验证工具专属输出；工具返回成功文本但不满足输出合同 MUST 视为失败，禁止保存为成功证据。query-builder 的中间产物 adapter 在提取生成结果后 MUST 还原文本转义，使产出的查询可直接执行；MUST NOT 把 `\n`、`\"` 等转义序列作为字面量传给下游工具。

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
- **WHEN** query-builder 的返回把生成的 CQL 嵌在转义文本中（例如围栏代码块里带 `\n` 与 `\"`）
- **THEN** 中间产物 adapter 还原转义后再产出查询，交给 SearchLog 的 Query 不含字面量转义序列

### Requirement: 工具纠错与重试有界且可审计
每个计划步骤 SHALL 最多执行三次 attempt。Pydantic validation 只负责产生结构化字段错误，独立错误策略 MUST 决定 retry、replan 或 permanent failure。可修正输入错误 MAY 将脱敏字段错误和允许 Schema 交给模型修正非权威参数；空结果 MAY 由 Replanner 调整查询；timeout、429 和临时 5xx SHALL 有界退避；配置缺失、401/403、owner 越权、工具未允许、runtime Schema 不兼容和其他永久 4xx MUST NOT 重试。Region、TopicId 以及已验证的跨步参数不得由纠错模型修改。每次 attempt MUST 写入 owner-scoped step、tool audit、持久事件和 checkpoint。失败分类 MUST 在脱敏前提下保留一段有界长度的服务端消息摘要，使失败原因可从 step、tool audit 与持久事件中读出；该摘要 MUST NOT 包含凭据、Region、TopicId 或其他敏感参数值。

#### Scenario: 第二次修正成功
- **WHEN** 首次参数校验失败，模型依据脱敏错误修正 Query 或可选范围且第二次通过
- **THEN** 系统记录一次 failed attempt 和一次 succeeded attempt，并只把真实成功输出保存为证据

#### Scenario: 三次仍失败
- **WHEN** 同一步达到三次上限仍未通过校验或真实调用
- **THEN** 步骤明确失败，Replanner 只能选择其他已登记真实证据；最终证据仍不足时不得进入可信报告或案例沉淀

#### Scenario: 永久错误不重试
- **WHEN** 工具失败原因是本地配置缺失、授权拒绝、owner 越权或 Schema 版本不兼容
- **THEN** 系统只记录一次 failed attempt 并立即进入安全失败处理，不把错误交给模型猜测修复

#### Scenario: 服务端返回可读错误
- **WHEN** 外部日志服务以执行错误形式返回语法错误、字段不存在或权限不足
- **THEN** step、tool audit 与持久事件中可见该错误的脱敏摘要，且不出现凭据、Region、TopicId 的具体值
