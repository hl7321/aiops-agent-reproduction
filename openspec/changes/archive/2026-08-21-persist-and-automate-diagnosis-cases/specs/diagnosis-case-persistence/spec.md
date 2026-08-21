## Purpose

本能力把成功且可追溯的 AIOps 诊断自动沉淀为 owner-scoped 结构化 case 与可索引知识文档，并保留独立的 legacy 手动保存路径，使真实历史故障能够参与后续检索。

## ADDED Requirements

### Requirement: 成功诊断自动生成结构化 case
系统 SHALL 只在诊断 task 为 `succeeded` 且存在成功最终 report 时自动创建 case；case MUST 保存 owner、唯一 source task、report、document、index task、alertName、service、keywords、rootCause、remediation、summary、当时查询到的 evidenceIds 与 createdAt。evidenceIds MAY 为空，失败、取消或无最终 report 的任务 MUST NOT 创建 case。

#### Scenario: 成功报告自动创建
- **WHEN** 诊断保存最终 report 并进入 succeeded
- **THEN** 系统自动创建一条关联该 task/report 的 case、知识文档和 durable index task

#### Scenario: 空证据仍诚实保存
- **WHEN** succeeded 诊断有最终 report 但当时 evidence 查询为空
- **THEN** case 使用空 evidenceIds 持久化且不伪造证据

#### Scenario: 非成功诊断不创建
- **WHEN** 诊断 failed、cancelled 或不存在成功最终 report
- **THEN** 系统不创建 case、case 文档或对应索引任务

### Requirement: 自动路径按 source task 并发幂等
自动 case 持久化 MUST 由独立边界执行，并以 owner-scoped source diagnostic task 的唯一性保证重复调用或并发调用只产生一条 case、一份活动文档和一个 index task。该幂等语义 MUST NOT 被描述为 legacy 手动保存的语义。

#### Scenario: 重试重复触发
- **WHEN** durable diagnosis retry 或 report 节点恢复后再次触发同一 source task
- **THEN** 自动路径返回既有 case 且不重复创建 document/index task

#### Scenario: 并发触发
- **WHEN** 两个并发事务尝试为同一 owner/task 自动持久化
- **THEN** 数据库唯一约束与冲突恢复使最终只存在一套 case/document/index 记录

### Requirement: case 文档通过标准知识与索引边界
系统 SHALL 从真实 report/evidence 提取结构化字段并生成 UTF-8 Markdown 文档，标记 `knowledgeType=diagnostic-case` 以及 source task/report/evidence metadata；文档 MUST 进入当前 owner 默认知识库并通过 P11 durable indexing 正常入队，禁止直接写 Milvus 或伪造索引成功。

#### Scenario: 生成可追溯 Markdown
- **WHEN** 自动 case 被创建
- **THEN** Markdown 包含真实告警、摘要、根因、处置和 evidenceIds，文档 metadata 可追溯 source diagnosis/report/evidence

#### Scenario: 下一轮检索命中
- **WHEN** case 文档索引成功且当前 owner 发起相关 knowledge_retrieval
- **THEN** 该文档与其他 owner 文档按同一 tenant-safe 混合检索流水线参与召回

### Requirement: legacy 手动保存保持独立
`POST /aiops/diagnostics/{id}:save-to-knowledge` SHALL 仅允许当前 owner 的 succeeded diagnosis，直接创建知识文档与 index task；重复内容 MUST 返回 `BUSINESS_CONFLICT`。该路径 MUST NOT 创建 `aiops_diagnostic_cases` 行，也 MUST NOT 与自动路径共享 service 或宣称相同幂等语义。

#### Scenario: 手动保存成功
- **WHEN** owner 对 succeeded diagnosis 调用 legacy 保存且内容未重复
- **THEN** API 返回新 document 与 index task，且 case 表没有因本调用新增行

#### Scenario: 手动重复内容
- **WHEN** 默认知识库已有相同内容的活动文档
- **THEN** API 返回 BUSINESS_CONFLICT 且不创建第二份文档、索引任务或 case

#### Scenario: 手动保存不可用诊断
- **WHEN** task 非 succeeded、没有 report 或不属于当前 owner
- **THEN** API 返回安全业务错误且不创建知识资产

### Requirement: case 查询保持 owner scope
系统 SHALL 提供 bearer-protected `GET /aiops/diagnostic-cases` 与 `GET /aiops/diagnostic-cases/{id}`；列表按 createdAt 与 id 确定性倒序，详情返回完整结构化字段，跨 owner 与不存在使用相同不可枚举错误。

#### Scenario: owner 查询 case
- **WHEN** 当前 owner 查询列表或自己的 case
- **THEN** API 使用共享 envelope/requestId 返回 owner-scoped DTO

#### Scenario: 跨用户查询
- **WHEN** user B 使用 user A 的 case id
- **THEN** API 返回与资源不存在相同的安全错误且不泄露字段

### Requirement: case schema 由 Alembic 权威管理
Alembic SHALL 创建 `aiops_diagnostic_cases`，其中 `task_id` 唯一并保存规范化 owner/report/document/index task 关联与结构化字段；keywords 与 evidenceIds 使用有界 JSON 数组，其他可查询关联使用列、外键和索引。知识文档 SHALL 保存有界 source metadata 并在索引时合并到 chunk metadata。

#### Scenario: fresh upgrade 与 metadata 一致
- **WHEN** 空数据库 upgrade head
- **THEN** case 表、唯一约束、外键、索引及文档 source metadata 列与 SQLAlchemy metadata 一致
