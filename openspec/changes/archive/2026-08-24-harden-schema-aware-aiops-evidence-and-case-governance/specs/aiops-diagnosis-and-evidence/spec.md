## MODIFIED Requirements

### Requirement: Planner 先获取 SOP 并发现 owner 工具
Planner SHALL 先以当前 owner scope 调用 `knowledge_retrieval` 检索 SOP，再发现当前 user enabled MCP connections 的真实工具，并将发现结果与 AIOps 只读取证能力 policy 取交集。Planner MUST 只根据输入告警、可选 query、SOP 引用以及交集工具的名称、描述、Schema 摘要和条件依赖生成有界计划。没有 SOP 结果 MAY 继续，但不得伪造 SOP。当前 CLS Profile MUST 恰好包含一个 SearchLog；未验证 Query 才要求先调用 query-builder，只有结论需要日志时序且命中提供定位字段时才要求 DescribeLogContext。其他步骤也 MUST 引用本 request 允许工具；模型输出不得扩大 owner、工具或权威参数权限。

#### Scenario: 有 SOP 且有 SearchLog
- **WHEN** owner 知识库返回 SOP 且本轮发现并允许 SearchLog
- **THEN** 最终计划保存 SOP 引用并恰好包含一个真实 SearchLog，其他能力只按查询来源和证据需要加入

#### Scenario: 没有 SOP
- **WHEN** owner-scoped knowledge retrieval 返回空结果但存在允许的 SearchLog
- **THEN** Planner 可继续生成有界计划，并明确记录没有 SOP 证据而不是生成虚假引用

#### Scenario: 缺少 SearchLog 工具
- **WHEN** 当前 owner 缺少当前 Profile 必需的 SearchLog
- **THEN** 任务以稳定 SearchLog 工具缺失错误失败；缺少条件工具只有在本轮条件成立时才构成对应能力不足

#### Scenario: 模型建议未注册工具
- **WHEN** Planner 输出未发现/未登记工具、多个 SearchLog 或违反本轮成立的条件依赖
- **THEN** 系统在最多三次内反馈脱敏校验错误要求修正，仍无效则失败且绝不调用该计划

### Requirement: Executor 和 Replanner 只承认真实结果
Executor SHALL 只调用当前 request 动态发现与 AIOps policy 交集中的工具，并为每次 attempt 持久化通用 tool audit、步骤状态与 checkpoint。所有允许工具输入 MUST 通过各自验证器，成功结果 MUST 先通过工具专属输出 adapter，再转换为中间产物或规范化证据；失败 MUST 保存安全错误分类并产生 failed 生命周期。Replanner SHALL 只依据计划、attempt、已完成步骤、真实证据、缺失能力和待支持 claim 决定继续、选择其他已登记工具或结束。SearchLog 是当前 Profile 的必需运行证据；DescribeLogContext 失败不得被伪造为成功，但只有本轮 claim 需要时序上下文且没有其他满足 policy 的独立证据时，才阻止 verified_evidence。

#### Scenario: 工具成功产生证据
- **WHEN** SearchLog 和本轮计划使用的其他证据工具都通过真实调用与各自输出校验
- **THEN** 系统保存对应 audits、attempts、typed evidence 和稳定跨步关联，辅助 query artifact 不冒充运行证据

#### Scenario: 工具失败
- **WHEN** DescribeLogContext 在有界尝试后仍失败
- **THEN** Replanner 可选择其他已登记的真实证据工具；若待支持的时序 claim 最终仍缺少充分证据，报告必须标记 insufficient_evidence 且不可提升，不得伪造上下文成功

#### Scenario: 无上下文仍有充分独立证据
- **WHEN** 当前 claim 不依赖事件前后顺序，或经过校验的多个日志命中与独立指标证据已满足 evidence policy
- **THEN** 系统不因未调用 DescribeLogContext 自动判定失败，但仍须把实际使用的 evidence links 交给报告门禁

#### Scenario: 当前 owner 工具隔离
- **WHEN** 模型试图使用另一个 user 的 MCP connection、知识引用或诊断 task
- **THEN** owner-scoped 查询不返回该资源，执行器不调用该工具且不泄露其存在

### Requirement: 报告使用固定中文结构和真实 provenance
报告生成器 SHALL 只把输入告警、真实 SOP 引用、最终计划和已持久化且通过合同校验的 evidence 提供给模型，并要求输出既有固定中文 Markdown 结构。每个关键结论 MUST 建立 report_evidence_link。报告 MUST 标记 `verified_evidence|insufficient_evidence|execution_failed` 信任状态；只有当前 Profile 的必需能力和每个 claim 的 evidence policy 均满足、所有确定性 claim 有真实链接且 `uncertainty=false` 时才能标记 `verified_evidence`。工具数量或单一工具名称不得单独决定可信状态。报告持久化不得自动触发案例或知识写入。

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

### Requirement: 模型失败使用诚实 fallback
当 report LLM 调用、结构校验或固定标题校验失败时，系统 SHALL 根据已持久化告警、计划、步骤和 evidence 生成不可提升的中文执行说明。说明 MUST 标记 `insufficient_evidence` 或 `execution_failed`、生成方式和不确定性，只引用已有 evidence，不得生成新根因、日志、指标、工具结果或伪造 provenance；SearchLog、配置、授权或 runtime 等不可恢复失败 MUST 使诊断失败，条件证据不足不得被 fallback 改写成 verified_evidence。

#### Scenario: 报告模型失败但已有证据
- **WHEN** 已收集部分真实 evidence 但报告模型调用失败
- **THEN** 系统可保存不可提升的说明和真实 links，但诊断不以可信报告成功完成

#### Scenario: 报告模型失败且无证据
- **WHEN** 模型失败且没有足以支持根因的 evidence
- **THEN** 说明只列告警、已执行步骤和失败原因，不编造任何产品结论或知识资产
