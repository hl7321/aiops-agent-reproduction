## ADDED Requirements

### Requirement: Timeline 展示 Schema-aware attempt 和条件证据门禁
AIOps timeline SHALL 以可读中文展示工具能力、attempt 序号、输入/输出校验错误分类、重试和本轮条件证据缺失；不得渲染 raw MCP JSON、完整参数值或工具输出。SearchLog 与按条件调用的 DescribeLogContext SHALL 可追溯。SearchLog、配置、权限或 runtime 永久失败 MUST 显示 diagnostic failed；条件证据不足 MUST 显示 insufficient_evidence，不得包装为 verified_evidence。

#### Scenario: 工具纠错后成功
- **WHEN** 一个 CLS 步骤首次校验失败、随后重试成功
- **THEN** timeline 显示失败分类、重试次数和最终成功证据关联，但不显示原始参数或响应 JSON

#### Scenario: 必需上下文失败
- **WHEN** DescribeLogContext 达到最大尝试次数仍失败且本轮 claim 需要事件时序、也没有满足 policy 的替代证据
- **THEN** 页面显示缺失的条件证据和 insufficient_evidence，不展示 verified_evidence 或确定性根因结论

#### Scenario: 不需要上下文的可信结论
- **WHEN** 当前 claim 不依赖时序上下文且其他经过验证的真实证据满足 policy
- **THEN** 页面不把未调用 DescribeLogContext 显示为错误，并按服务端 trustState 展示报告

### Requirement: 报告可信状态和知识提升保持诚实
工作区 SHALL 区分 verified_evidence、insufficient_evidence 与 execution_failed。只有 verified_evidence、uncertainty=false 且当前 owner 已保存 positive report feedback 时，页面才可发起显式知识提升；服务端拒绝时 MUST 保留反馈和可重试状态。精确重复 SHALL 打开既有 canonical case，语义相似 SHALL 展示候选并要求用户选择，前端不得自动合并或假装新 case 已写入。

#### Scenario: 认可后提升可信报告
- **WHEN** 用户对 verified_evidence 报告提交 positive feedback 并点击保存为可信案例
- **THEN** 页面调用真实提升 API，并在成功后刷新 case 与 provenance

#### Scenario: 不可信报告不可提升
- **WHEN** 报告 uncertainty=true、信任状态非 verified_evidence 或没有 positive feedback
- **THEN** 页面明确解释不可提升原因且不发起 case/document/index 写入

#### Scenario: 语义相似待人工选择
- **WHEN** 提升 API 返回同 owner 的相似 canonical case 候选
- **THEN** 页面要求用户明确选择合并或新建，未选择前不显示知识沉淀成功
