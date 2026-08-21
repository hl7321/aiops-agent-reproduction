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
Planner SHALL 先以当前 owner scope 调用 `knowledge_retrieval` 检索 SOP，再发现当前 user enabled MCP connections 的真实工具，并只根据输入告警、可选 query、SOP 引用和实际注册工具生成有界计划。没有 SOP 结果 MAY 继续，但不得伪造 SOP。最终有效计划 MUST 包含且只包含一个真实 SearchLog 类工具步骤，其他工具步骤也 MUST 引用本 request 已注册工具；模型输出不得扩大 owner 或工具权限。

#### Scenario: 有 SOP 且有 SearchLog
- **WHEN** owner 知识库返回 SOP 引用且 enabled MCP 发现一个 SearchLog 类工具
- **THEN** 最终计划保存 SOP 引用并恰好包含一个指向该真实工具的日志搜索步骤

#### Scenario: 没有 SOP
- **WHEN** owner-scoped knowledge retrieval 返回空结果但存在可用 SearchLog 工具
- **THEN** Planner 可继续生成有界计划，并明确记录没有 SOP 证据而不是生成虚假引用

#### Scenario: 缺少 SearchLog 工具
- **WHEN** 当前 owner 没有发现任何可用 SearchLog 类工具
- **THEN** 任务以稳定 `SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE` 工具缺失错误失败，不生成日志证据或诊断报告

#### Scenario: 模型建议未注册工具
- **WHEN** Planner 模型输出包含未在本 request 注册表中的工具或多个 SearchLog 步骤
- **THEN** 系统拒绝该计划或在上限内要求重规划，绝不调用未注册工具

### Requirement: Executor 和 Replanner 只承认真实结果
Executor SHALL 只调用当前 owner 的 knowledge retrieval 或本 request 实际发现的 MCP 工具，并为每次调用持久化通用 tool audit。成功工具结果 MUST 转换为规范化证据；失败 MUST 保存安全错误并产生 failed 工具生命周期。Replanner SHALL 只依据计划、已完成步骤和现有证据决定继续、调整或报告，不得把失败步骤改写为成功、生成假工具输出或补造分数。

#### Scenario: 工具成功产生证据
- **WHEN** Executor 调用真实 SearchLog 或知识工具并获得结果
- **THEN** 系统保存 completed audit、步骤结果和对应 evidence，且三者通过稳定标识可追溯

#### Scenario: 工具失败
- **WHEN** MCP、知识、timeout 或 payload 解析失败
- **THEN** 系统保存 failed audit/step 和安全错误，Replanner 只能基于其余真实证据继续或报告不确定性

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
系统 SHALL 提供 bearer-protected `POST /aiops/diagnostics`、`GET /aiops/diagnostics`、`GET /aiops/diagnostics/{id}`、`GET /aiops/diagnostics/{id}/evidence-chain` 与 `POST /aiops/diagnostics/{id}:stream`。创建输入 MUST 是有界的 ActiveAlert 快照和可选 query；列表按 updatedAt 与 id 确定性倒序；详情返回 task、backgroundJob、步骤和 nullable report；证据链返回规范化 evidence、report links 与 tool audits。所有响应使用共享 envelope/requestId 和 owner scope。

#### Scenario: 创建诊断
- **WHEN** 已认证用户提交合法的真实告警快照和可选 query
- **THEN** API 返回统一 success envelope，其中包含 accepted task 和 queued backgroundJob

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
报告生成器 SHALL 只把输入告警、真实 SOP 引用、最终计划和已持久化 evidence 提供给模型，并要求输出固定中文 Markdown：`# 告警分析报告`、`## 📋 活跃告警清单`、每条告警对应的 `## 🔍 告警根因分析N`（详情/症状/日志证据/根因结论）、`## 🛠️ 处理方案执行N`（已执行步骤/建议/预期效果），最后为 `## 📊 结论`（整体评估/关键发现/后续建议/风险评估）。每个关键结论 MUST 建立 report_evidence_link；证据不足 MUST 明确不确定性，禁止把建议写成已执行事实。

#### Scenario: 多告警报告
- **WHEN** 任务包含两条告警和足够真实证据
- **THEN** 报告包含两组编号根因分析/处理方案、固定结论结构，并且关键结论分别链接现有 evidence id

#### Scenario: 证据不足
- **WHEN** 日志或 SOP 证据不能支持确定根因
- **THEN** 对应根因结论和整体风险明确标注不确定性，不生成无 evidence link 的确定性关键结论

#### Scenario: provenance 指向真实记录
- **WHEN** 客户端读取 evidence-chain
- **THEN** 每个 report link 指向同 owner、同 diagnostic task 的现有 evidence，不能链接任意或跨租户记录

### Requirement: 模型失败使用诚实 fallback
当 report LLM 调用、结构校验或固定标题校验失败时，系统 SHALL 根据已持久化告警、计划、步骤和 evidence 生成同一固定标题结构的中文 fallback。fallback MUST 标记生成方式和不确定性，只引用已有 evidence，不得生成新根因、日志、指标、工具结果或伪造 provenance；若 SearchLog 缺失则任务必须在报告前失败，不能用 fallback 掩盖工具缺失。

#### Scenario: 报告模型失败但已有证据
- **WHEN** 图已收集真实 evidence 但报告模型调用失败
- **THEN** 系统保存结构化 fallback 和对应真实 links，任务可成功完成但报告明确标注自动推断受限

#### Scenario: 报告模型失败且无证据
- **WHEN** 模型失败且没有足以支持根因的 evidence
- **THEN** fallback 只列告警、已执行步骤和“证据不足，无法确定根因”，不编造任何产品结论

### Requirement: 诊断输入、错误和日志保持脱敏
诊断持久输入、event、audit、checkpoint、evidence 和报告 MUST 排除凭据、MCP URL secret、完整未筛选工具 payload 和模型密钥。结构化运行日志只能记录 task/job/tool 名、参数键、状态和耗时，不得记录 query、完整参数值、原始日志全文、prompt 或模型输出。单元测试 MAY 注入 fake provider/MCP 边界，但 fake 结果 MUST 明确是测试 fixture，不能在生产 factory、fallback 或产品报告中生成。

#### Scenario: 工具错误包含 secret
- **WHEN** fake MCP 或模型异常文本包含当前配置凭据
- **THEN** 持久 failureReason、event、audit 和 API/SSE 错误均替换为 `[redacted]`

#### Scenario: 普通启动无外部调用
- **WHEN** import 诊断模块或启动未创建任务的 FastAPI app
- **THEN** 不发现 MCP、不调用 Qwen/knowledge、不执行图，也不生成任何诊断证据
