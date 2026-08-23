## MODIFIED Requirements

### Requirement: 成功诊断自动生成结构化 case
系统 SHALL 停止在诊断完成时自动创建 case。只有 report 属于当前 owner、信任状态为 `verified_evidence`、`uncertainty=false`、存在完整 provenance，且当前 owner 已提交有效的 positive diagnostic_report feedback 后，显式提升操作才可创建或关联 canonical case。失败、取消、fallback、证据不足、执行失败、未反馈或 negative feedback 的报告 MUST NOT 创建 case、知识文档或 index task。

#### Scenario: 认可可信报告后提升
- **WHEN** owner 对 verified_evidence 报告提交 positive feedback 并显式执行提升
- **THEN** 系统创建或关联 canonical case、知识文档和 durable index task，并记录认可反馈与来源 provenance

#### Scenario: 未认可报告不创建
- **WHEN** 报告没有反馈、反馈为 negative、uncertainty=true 或信任状态非 verified_evidence
- **THEN** 提升被拒绝且不创建 case、文档、索引任务或向量

#### Scenario: 诊断完成不自动写入
- **WHEN** 诊断生成任意最终报告并进入终态
- **THEN** report 节点不调用 case 持久化，知识库保持不变直到显式提升

#### Scenario: 成功报告自动创建
- **WHEN** 诊断保存最终 report 并进入 succeeded，但 owner 尚未提交 positive feedback 和显式提升
- **THEN** 系统不再自动创建 case、知识文档或 durable index task

#### Scenario: 空证据仍诚实保存
- **WHEN** succeeded 诊断有最终 report 但 evidence 为空
- **THEN** 报告只能保持证据不足且不可提升，系统不以空 evidenceIds 自动创建 case

#### Scenario: 非成功诊断不创建
- **WHEN** 诊断 failed、cancelled 或不存在成功最终 report
- **THEN** 系统不创建 case、case 文档或对应索引任务

### Requirement: 自动路径按 source task 并发幂等
显式提升 MUST 同时保证同一 owner/source report 幂等和同一 owner/incident fingerprint 的 canonical 唯一性。重复调用或并发调用只产生一条 canonical case、一份活动知识文档和一个活动 index task；不同诊断任务的精确重复 MUST 追加 provenance source，而不是创建第二份可检索内容。

#### Scenario: 同一报告重复提升
- **WHEN** owner 重复或并发提升同一 report
- **THEN** 系统返回既有 canonical case，且不重复创建 document/index task

#### Scenario: 不同任务精确重复
- **WHEN** 两个诊断任务生成相同 incident fingerprint 和 knowledge fingerprint 的可信认可报告
- **THEN** 第二次提升只追加 task/report/evidence source 关系，不新增 case 文档或向量

#### Scenario: 重试重复触发
- **WHEN** owner 对同一 source report 重复发起显式提升
- **THEN** 系统返回既有 canonical case 且不重复创建 document/index task

#### Scenario: 并发触发
- **WHEN** 两个并发事务提升同一 owner/report 或相同 canonical fingerprint
- **THEN** 数据库唯一约束与冲突恢复使最终只存在一套 case/document/index 记录

### Requirement: case 文档通过标准知识与索引边界
系统 SHALL 从可信 report/evidence 生成 UTF-8 Markdown 文档，标记 `knowledgeType=diagnostic-case`、canonical fingerprint 和 source provenance；文档 MUST 进入当前 owner 默认知识库并通过 durable indexing 入队，禁止直接写 Milvus。相同 canonical case 的重试 MUST 复用文档并通过 owner-scoped 删除旧 chunks 后单次写入，语义相似但 fingerprint 不同的候选 MUST 要求人工选择合并或新建，不得自动重复沉淀。

#### Scenario: 生成可追溯 Markdown
- **WHEN** canonical case 首次被批准创建
- **THEN** Markdown 包含真实告警、摘要、根因、处置和 evidenceIds，metadata 可追溯全部 source diagnosis/report/evidence

#### Scenario: semantic similar 候选
- **WHEN** 新报告与既有 case 语义相似但不满足精确 fingerprint
- **THEN** 提升返回候选与待决定状态，不创建文档/index task，等待 owner 明确选择

#### Scenario: 下一轮检索命中唯一内容
- **WHEN** canonical case 文档索引成功且当前 owner 发起相关 knowledge_retrieval
- **THEN** 同一事实只以 canonical 文档参与 tenant-safe 召回，source provenance 不产生重复向量文档

#### Scenario: 下一轮检索命中
- **WHEN** canonical case 文档索引成功且当前 owner 发起相关 knowledge_retrieval
- **THEN** 该唯一 canonical 文档与其他 owner 文档按同一 tenant-safe 混合检索流水线参与召回

## ADDED Requirements

### Requirement: canonical case 来源关系规范化持久化
Alembic SHALL 为 case 增加稳定 incident fingerprint、knowledge fingerprint 和提升状态，并创建规范化 source 关系保存 owner、case、diagnostic task、report、approval feedback 及当时 evidence IDs。随机 task/report/evidence id MUST NOT 进入 fingerprint；owner 与 fingerprint 的唯一约束 MUST 阻止并发重复。

#### Scenario: fresh database upgrade
- **WHEN** 空数据库执行 Alembic upgrade head
- **THEN** canonical fingerprint、唯一约束、source provenance 外键/索引与 SQLAlchemy metadata 一致

#### Scenario: 跨 owner 相同故障
- **WHEN** 两个用户各自提升相同规范化故障
- **THEN** 每个 owner 拥有独立 canonical case 和向量文档，彼此不可查询或合并
