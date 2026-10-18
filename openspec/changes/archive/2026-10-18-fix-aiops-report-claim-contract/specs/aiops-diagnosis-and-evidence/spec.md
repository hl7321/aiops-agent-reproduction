# Spec Delta

## MODIFIED Requirements

### Requirement: 报告使用固定中文结构和真实 provenance

报告生成器 SHALL 只把输入告警、真实 SOP 引用、最终计划、执行结果和已持久化且通过合同校验的 evidence 提供给模型，并要求输出既有固定中文 Markdown 结构。每个关键结论 MUST 建立 report_evidence_link。报告 MUST 标记 `verified_evidence|insufficient_evidence|execution_failed` 信任状态；只有当前 Profile 的必需能力和每个 claim 的 evidence policy 均满足、所有确定性 claim 有真实链接且 `uncertainty=false` 时才能标记 `verified_evidence`。工具数量或单一工具名称不得单独决定可信状态。报告持久化不得自动触发案例或知识写入。

`claims[].claimKey` 是报告内部用于把结论与证据关联的短标识，MUST NOT 承担结论正文。服务端 MUST 对超过存储上限的标识做确定性归一化，MUST NOT 因标识长度拒绝整份报告；归一化后同一报告内出现重复标识时 MUST 追加稳定后缀去重。证据 ID 必须真实存在、固定中文标题与逐告警编号必须齐全等校验 MUST 保持严格。

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

#### Scenario: 报告使用执行结果说明未完成步骤

- **WHEN** 执行结果中存在未执行或失败的步骤
- **THEN** 报告依据该执行结果如实说明哪些步骤未完成及其失败类别，不虚构执行成功

#### Scenario: 超长 claim 标识被归一化

- **WHEN** 报告模型交回的 `claimKey` 超过存储上限，但其余结构合法且证据 ID 真实存在
- **THEN** 服务端以确定性规则归一化该标识并保存模型报告，任务不因标识长度降级为兜底报告

#### Scenario: 归一化后标识重名

- **WHEN** 同一报告内两个不同 claim 的超长标识归一化后完全相同
- **THEN** 服务端为后续 claim 追加稳定后缀，所有 report→evidence 链接成功保存且不违反唯一约束

#### Scenario: 引用不存在的证据仍然拒绝

- **WHEN** 报告 claim 引用了本轮不存在的 evidence ID
- **THEN** 该报告仍然校验失败并走兜底，不因标识归一化而放行伪造 provenance

### Requirement: 模型失败使用诚实 fallback

当 report LLM 调用、结构校验或固定标题校验失败时，系统 SHALL 根据已持久化告警、计划、步骤和 evidence 生成不可提升的中文执行说明。说明 MUST 标记 `insufficient_evidence` 或 `execution_failed`、生成方式和不确定性，只引用已有 evidence，不得生成新根因、日志、指标、工具结果或伪造 provenance；SearchLog、配置、授权或 runtime 等不可恢复失败 MUST 使诊断失败，条件证据不足不得被 fallback 改写成 verified_evidence。

**诊断的最终状态 MUST 由报告的信任状态决定，而不是由"报告已生成"决定**：

- `verified_evidence` → 任务可标记 `succeeded`。
- `insufficient_evidence` → 任务 MUST NOT 标记 `succeeded`。若本轮证据评估原本为 `verified_evidence`、仅因报告模型调用或结构校验失败而降级，MUST 使用 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`；若本轮证据本来就不足，MUST 使用 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`。
- `execution_failed` → 任务 MUST 标记 `failed`。

fallback 说明本身 MUST 保持可读，使用户能看到哪些步骤执行过、失败在哪里、为什么结论不可信。

#### Scenario: 报告模型失败但已有证据

- **WHEN** 已收集部分真实 evidence 但报告模型调用失败
- **THEN** 系统可保存不可提升的说明和真实 links，但诊断不以可信报告成功完成，任务状态按信任状态表达而不是 succeeded

#### Scenario: 报告模型失败且无证据

- **WHEN** 模型失败且没有足以支持根因的 evidence
- **THEN** 说明只列告警、已执行步骤和失败原因，不编造任何产品结论或知识资产

#### Scenario: 证据不足不标记成功

- **WHEN** 报告生成成功但信任状态为 insufficient_evidence
- **THEN** 任务最终状态表达"证据不足"而不是 succeeded，且客户端可据此区分"得到可信结论"与"未能得出结论"

#### Scenario: 证据充分但报告生成失败

- **WHEN** 本轮已拿到真实日志命中（证据评估为 verified_evidence），但报告模型调用或结构校验失败
- **THEN** 兜底报告仍为 insufficient_evidence，任务失败码为 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`，而不是 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`
