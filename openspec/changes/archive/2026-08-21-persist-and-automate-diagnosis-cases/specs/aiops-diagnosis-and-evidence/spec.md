## MODIFIED Requirements

### Requirement: 报告使用固定中文结构和真实 provenance
报告生成器 SHALL 只把输入告警、真实 SOP 引用、最终计划和已持久化 evidence 提供给模型，并要求输出固定中文 Markdown：`# 告警分析报告`、`## 📋 活跃告警清单`、每条告警对应的 `## 🔍 告警根因分析N`（详情/症状/日志证据/根因结论）、`## 🛠️ 处理方案执行N`（已执行步骤/建议/预期效果），最后为 `## 📊 结论`（整体评估/关键发现/后续建议/风险评估）。每个关键结论 MUST 建立 report_evidence_link；证据不足 MUST 明确不确定性，禁止把建议写成已执行事实。最终 report 保存且 task 进入 succeeded 后，report 节点 MUST 调用独立自动 case 持久化边界；自动持久化失败时本次诊断不得发出成功 complete。

#### Scenario: 多告警报告
- **WHEN** 任务包含两条告警和足够真实证据
- **THEN** 报告包含两组编号根因分析/处理方案、固定结论结构，并且关键结论分别链接现有 evidence id

#### Scenario: 证据不足
- **WHEN** 日志或 SOP 证据不能支持确定根因
- **THEN** 对应根因结论和整体风险明确标注不确定性，不生成无 evidence link 的确定性关键结论

#### Scenario: provenance 指向真实记录
- **WHEN** 客户端读取 evidence-chain
- **THEN** 每个 report link 指向同 owner、同 diagnostic task 的现有 evidence，不能链接任意或跨租户记录

#### Scenario: 成功报告触发自动 case
- **WHEN** report 与 links 已持久化且 task 成功转换为 succeeded
- **THEN** report 节点触发自动 case/document/index 持久化，成功后才继续发送完成事件
