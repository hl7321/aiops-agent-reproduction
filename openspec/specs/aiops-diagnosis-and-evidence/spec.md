## Purpose

本能力让每个已认证用户以 durable job 运行可恢复、证据优先的 AIOps 诊断，并把计划、步骤、工具审计、证据、checkpoint、报告及其引用关系规范化保存，确保报告结论只能建立在真实输入和真实工具结果之上。

# AIOps 诊断与证据链规格
## Requirements
### Requirement: 诊断由有界可恢复图执行
系统 SHALL 按 `START→planner→executor→replanner→(executor|report)→END` 执行诊断图。计划步数和重规划次数 MUST 各有明确正数上限；到达上限时 MUST 进入基于已有证据的报告或安全失败，禁止无限循环。每个节点完成后 MUST 持久化 owner-scoped checkpoint，使 worker 在 lease 过期、进程重启或 retry 后从最后一个完整节点恢复，而不是把未完成节点虚构为成功。

#### Scenario: 正常图路径
- **WHEN** planner 生成有效计划、executor 获得真实证据且 replanner 判定证据足够
- **THEN** 节点按规定顺序进入 report，并且 checkpoint 记录每个已完成节点和对应计划版本

#### Scenario: 重规划达到上限
- **WHEN** replanner 连续调整计划并达到配置的最大重规划次数
- **THEN** 图不再进入 executor，无证据时安全失败，有证据时生成明确不确定性的诚实报告

#### Scenario: worker 重启恢复
- **WHEN** worker 在一个节点完成并保存 checkpoint 后退出，随后 durable job lease 被回收
- **THEN** 新 worker 从该 checkpoint 恢复未完成流程，不重复声明已经完成的步骤或丢失已有证据

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

### Requirement: 诊断完全复用 durable job 生命周期
创建诊断 SHALL 原子地保存 diagnostic task 并入队 kind=`aiops_diagnosis`、resourceType=`diagnostic_task`、resourceId=taskId 的 background job。diagnostic status MUST 为 `accepted|running|succeeded|failed|cancelled`，分别映射 job/SSE 的 `queued|running|succeeded|failed|cancelled`；创建响应 MUST 同时返回 task 与 backgroundJob。客户端断开不得取消任务；取消和 retry MUST 只复用 `/background-jobs/{jobId}:cancel|:retry`，不得增加诊断专用 cancel/retry endpoint。

#### Scenario: 创建并断开客户端
- **WHEN** owner 创建诊断后立即断开连接
- **THEN** task 为 accepted、job 为 queued，worker 仍能领取并继续执行

#### Scenario: 协作取消
- **WHEN** owner 通过通用 background-job API 请求取消运行中的诊断
- **THEN** handler 在安全检查点停止，job/SSE 与 diagnostic task 最终均为 cancelled

#### Scenario: 通用 retry
- **WHEN** owner 对 failed 或 cancelled job 调用通用 retry
- **THEN** 新 background job 仍关联同一 diagnostic task，并从持久 checkpoint/证据恢复或安全重做未完成节点

### Requirement: 诊断过程使用规范化 owner-scoped 持久化
Alembic SHALL 管理 `diagnostic_tasks`、`diagnostic_steps`、`diagnostic_evidence`、`diagnostic_reports`、`report_evidence_links` 与 `graph_checkpoints`。系统 MUST 分别保存安全原始输入、计划及版本、步骤、通用工具审计、`alert|knowledge|log|metric` 证据、checkpoint、报告和 report→evidence links；有查询、排序、关联需求的数据 MUST 使用规范化列/外键/索引，不得把完整证据链塞进单个不可查询 JSON。所有 Repository list/get/write MUST 显式以 `owner_user_id` 约束。

#### Scenario: fresh database upgrade
- **WHEN** 空数据库执行 Alembic upgrade head
- **THEN** 六张诊断表、约束、索引和通用 audit 的 diagnostic parent 均可用，metadata 与迁移一致

#### Scenario: 保存多类证据
- **WHEN** 一个诊断收集告警、SOP、日志和指标证据
- **THEN** 每条证据拥有独立 kind、source、摘要/内容、metadata、step/tool 关联和时间，不依赖解析整任务 JSON 查询

#### Scenario: 跨租户查询
- **WHEN** user B 使用 user A 的 task、step、evidence、report 或 checkpoint id 查询或写入
- **THEN** owner-scoped Repository 与 API 返回不可枚举错误且不修改任何 A 数据

### Requirement: 诊断 API 暴露任务和完整证据链
系统 SHALL 提供 bearer-protected `POST /aiops/diagnostics`、`GET /aiops/diagnostics`、`GET /aiops/diagnostics/{id}`、`GET /aiops/diagnostics/{id}/evidence-chain` 与 `POST /aiops/diagnostics/{id}:stream`。创建输入 MUST 包含非空手工 query 或至少一条有界 ActiveAlert 快照，允许同时提供两者；当前合同不得增加独立 context 字段。列表按 updatedAt 与 id 确定性倒序；详情返回 task、backgroundJob、步骤和 nullable report；证据链返回规范化 evidence、report links 与 tool audits。所有响应使用共享 envelope/requestId 和 owner scope。

#### Scenario: 创建诊断
- **WHEN** 已认证用户提交合法的真实告警快照和可选 query，或提交非空手工 query 和空 alerts
- **THEN** API 返回统一 success envelope，其中包含 accepted task 和 queued backgroundJob，且不构造默认告警

#### Scenario: 通过手工 query 创建诊断
- **WHEN** 已认证用户提交非空 query 且未选择告警
- **THEN** API 使用同一 endpoint 创建 accepted task 和 queued backgroundJob，不构造默认告警

#### Scenario: 读取证据链
- **WHEN** owner 查询已产生证据的诊断
- **THEN** API 返回可按 step、tool call、report claim 和 evidence id 追溯的规范化链条

#### Scenario: 跨用户 API 访问
- **WHEN** 另一个用户请求 task 详情、证据链或 stream
- **THEN** API 使用与资源不存在相同的安全错误，不泄露任务状态或内容

### Requirement: 持久流只复用共享 SSE union
诊断 stream SHALL 从关联 background job 的持久 events 按 sequence 回放并轮询新事件，支持从 `afterSequence=0` 或指定 sequence 恢复。它 MUST 只发送 `task.status`、`tool.call`、`reference.source`、`report`、`complete`、`error`；计划、步骤和重规划进度 MUST 使用 typed `task.status.data.message/progress`，不得增加 plan/step/replan 私有 event type。工具、知识/日志证据和报告分别使用对应共享事件；terminal complete MUST 恰好一次，SSE 断开不得取消 job。

#### Scenario: 从头重放
- **WHEN** 客户端以 afterSequence=0 连接已运行一段时间的任务
- **THEN** stream 按持久 sequence 有序回放已有事件，再轮询新事件直到 terminal

#### Scenario: 从中间恢复
- **WHEN** 客户端以最后已处理 sequence 重新连接
- **THEN** stream 只发送更大 sequence 的事件，不重复旧事件且不改变 task

#### Scenario: 表达计划进度
- **WHEN** planner、executor 或 replanner 保存计划版本和步骤进度
- **THEN** 客户端收到 task.status 的中文 message 与 0..100 progress，不出现未登记 SSE type

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

### Requirement: 诊断输入、错误和日志保持脱敏
诊断持久输入、event、audit、checkpoint、evidence 和报告 MUST 排除凭据、MCP URL secret、完整未筛选工具 payload 和模型密钥。结构化运行日志只能记录 task/job/tool 名、参数键、状态和耗时，不得记录 query、完整参数值、原始日志全文、prompt 或模型输出。单元测试 MAY 注入 fake provider/MCP 边界，但 fake 结果 MUST 明确是测试 fixture，不能在生产 factory、fallback 或产品报告中生成。

#### Scenario: 工具错误包含 secret
- **WHEN** fake MCP 或模型异常文本包含当前配置凭据
- **THEN** 持久 failureReason、event、audit 和 API/SSE 错误均替换为 `[redacted]`

#### Scenario: 普通启动无外部调用
- **WHEN** import 诊断模块或启动未创建任务的 FastAPI app
- **THEN** 不发现 MCP、不调用 Qwen/knowledge、不执行图，也不生成任何诊断证据
