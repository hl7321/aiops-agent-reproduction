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

Planner SHALL 先以当前 owner scope 调用 `knowledge_retrieval` 检索 SOP，再发现当前 user enabled MCP connections 的真实工具。Planner MUST 只根据输入告警、可选 query、SOP 引用，以及本轮真实发现的只读工具的名称、描述和完整参数 schema 生成有界计划；工具集合 MUST NOT 与静态名单取交集，MUST NOT 包含已被判定为当前数据源不可用的退役工具。

Planner MUST NOT 输出任何工具参数值：计划生成时后续步骤的真实产出尚不存在，参数由 Executor 在该步骤执行时提供。没有 SOP 结果 MAY 继续，但不得伪造 SOP。当前 CLS Profile MUST 恰好包含一个 SearchLog；只要计划包含日志检索，MUST 在它之前包含恰好一个 query-builder 步骤，与该次诊断是否携带用户原始查询无关。

上下文能力由数据源决定，且不再作为计划的一部分：当前数据源的日志检索结果本身携带链路顺序，需要证明前后过程时 Planner 直接依据检索结果规划，MUST NOT 规划专门的日志上下文工具，也 MUST NOT 输出任何时序需求标志。其他步骤也 MUST 引用本轮真实发现的只读工具；模型输出不得扩大 owner、工具或权威参数权限。

#### Scenario: 有 SOP 且有 SearchLog

- **WHEN** owner 知识库返回 SOP 且本轮发现可用的 SearchLog
- **THEN** 最终计划保存 SOP 引用并恰好包含一个真实 SearchLog，且该 SearchLog 之前存在一个 query-builder 步骤

#### Scenario: 没有 SOP

- **WHEN** owner-scoped knowledge retrieval 返回空结果但存在可用的 SearchLog
- **THEN** Planner 可继续生成有界计划，并明确记录没有 SOP 证据而不是生成虚假引用

#### Scenario: 缺少 SearchLog 工具

- **WHEN** 当前 owner 的真实发现结果中缺少当前 Profile 必需的 SearchLog
- **THEN** 任务以稳定 SearchLog 工具缺失错误失败；缺少条件工具只有在本轮条件成立时才构成对应能力不足

#### Scenario: 模型建议未注册工具

- **WHEN** Planner 输出真实发现之外的只读工具、已被退役的工具、多个 SearchLog，或违反本轮成立的条件依赖
- **THEN** 系统在最多三次内反馈脱敏校验错误要求修正，仍无效则失败且绝不调用该计划

#### Scenario: 计划不携带参数

- **WHEN** Planner 生成任何一份可执行计划
- **THEN** 计划中的每一步只包含工具名、用途与顺序，不含任何参数值

#### Scenario: 上下文已在检索结果中

- **WHEN** 结论需要证明事件前后顺序，而日志上下文工具在当前数据源已退役
- **THEN** 计划以单次日志检索的结果作为前后过程依据，不包含上下文工具步骤，也不声明任何时序需求

### Requirement: Executor 和 Replanner 只承认真实结果

Executor SHALL 只调用本轮真实发现的只读工具，并为每次 attempt 持久化通用 tool audit、步骤状态与 checkpoint。Executor MUST 按其收到的计划逐步执行，不选择工具、不改变步骤顺序、不自行增加步骤；需要改变计划时必须交回 Replanner 处理。

Executor SHALL 在每一步执行前，依据该工具的完整参数说明、整份计划、前面步骤的真实产出与输入告警生成该步参数，并通过该工具真实 schema 的通用入参校验后才调用。成功结果 MUST 先通过工具专属输出 adapter（未登记 adapter 的工具按其产物类型规则处理），再转换为中间产物或规范化证据；失败 MUST 保存安全错误分类并产生 failed 生命周期。

**计划必须执行完毕。** 某个步骤的尝试次数耗尽时，Executor MUST 如实记录该步失败，并 MUST 把进度推进到下一步继续执行；MUST NOT 因为一步失败就把控制权提前交给 Replanner。只有计划中的每一步都被处理过（成功、失败或按规则跳过）之后，才把完整执行结果交给 Replanner。

Replanner SHALL 只做代码级验证：依据完整执行结果与已持久化证据判断是继续执行剩余步骤还是转入报告。其路由 MUST 只取决于进度与证据，MUST NOT 因为"存在失败的步骤"而提前转报告；步骤失败信息保留给报告说明使用。Replanner MUST NOT 调用模型、MUST NOT 改写计划。SearchLog 是当前 Profile 的必需运行证据；**证据充分性由真实日志命中决定，不再要求日志上下文产物作为时序结论的前提**，也不得因为缺少当前数据源无法提供的证据形态而阻止 `verified_evidence`。

#### Scenario: 工具成功产生证据

- **WHEN** SearchLog 和本轮计划使用的其他证据工具都通过真实调用与各自输出校验
- **THEN** 系统保存对应 audits、attempts、typed evidence 和稳定跨步关联，辅助 query artifact 不冒充运行证据

#### Scenario: 工具失败

- **WHEN** 计划中某个工具在有界尝试后仍失败
- **THEN** 执行结果如实记录该步失败与其类别；其余步骤继续执行；最终证据是否充分由真实日志命中决定，不得伪造任何未取得的证据

#### Scenario: 无上下文仍有充分独立证据

- **WHEN** 本轮拿到了真实日志命中，但没有日志上下文产物
- **THEN** 系统不因缺少上下文产物判定失败，证据状态由真实命中决定，并把实际使用的 evidence links 交给报告门禁

#### Scenario: 当前 owner 工具隔离

- **WHEN** 模型试图使用另一个 user 的 MCP connection、知识引用或诊断 task
- **THEN** owner-scoped 查询不返回该资源，执行器不调用该工具且不泄露其存在

#### Scenario: 执行者按计划逐步执行

- **WHEN** Executor 收到一份包含多个步骤的计划
- **THEN** 它按计划给定的工具与顺序逐步执行，不选择其他工具、不调整顺序、不追加计划外的步骤

#### Scenario: 参数来自前序真实产出

- **WHEN** 当前步骤需要前面步骤产生的值
- **THEN** Executor 从前面步骤的真实产出中取值填入，并通过该工具真实 schema 校验后才调用

#### Scenario: 某一步失败后其余步骤继续执行

- **WHEN** 计划中某一步在尝试上限内仍未成功，且其后仍有未执行的步骤
- **THEN** Executor 记录该步失败并把进度推进到下一步，继续执行剩余的每一步，直到计划全部处理完毕才交给 Replanner

#### Scenario: Replanner 不因失败标记提前结束

- **WHEN** 执行结果中存在失败步骤，但计划仍有未执行的步骤
- **THEN** Replanner 继续把控制权交给 Executor，而不是直接转入报告

#### Scenario: Replanner 本轮不改计划

- **WHEN** Replanner 依据执行结果判断证据仍不足以支撑结论
- **THEN** 它按代码规则选择继续执行剩余步骤或转入报告，不调用模型、不生成新计划

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

报告生成器 SHALL 只把输入告警、真实 SOP 引用、最终计划、执行结果和已持久化且通过合同校验的 evidence 提供给模型，并要求输出既有固定中文 Markdown 结构。每个关键结论 MUST 建立 report_evidence_link。报告 MUST 标记 `verified_evidence|insufficient_evidence|execution_failed` 信任状态；只有当前 Profile 的必需能力和每个 claim 的 evidence policy 均满足、所有确定性 claim 有真实链接且 `uncertainty=false` 时才能标记 `verified_evidence`。工具数量或单一工具名称不得单独决定可信状态。报告持久化不得自动触发案例或知识写入。

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

### Requirement: 模型失败使用诚实 fallback

当 report LLM 调用、结构校验或固定标题校验失败时，系统 SHALL 根据已持久化告警、计划、步骤和 evidence 生成不可提升的中文执行说明。说明 MUST 标记 `insufficient_evidence` 或 `execution_failed`、生成方式和不确定性，只引用已有 evidence，不得生成新根因、日志、指标、工具结果或伪造 provenance；SearchLog、配置、授权或 runtime 等不可恢复失败 MUST 使诊断失败，条件证据不足不得被 fallback 改写成 verified_evidence。

**诊断的最终状态 MUST 由报告的信任状态决定，而不是由"报告已生成"决定**：

- `verified_evidence` → 任务可标记 `succeeded`。
- `insufficient_evidence` → 任务 MUST NOT 标记 `succeeded`；MUST 以共享契约中表达"证据不足"的既有语义收尾，使客户端能区分"诊断成功"与"未能得出可信结论"。
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

### Requirement: 诊断输入、错误和日志保持脱敏
诊断持久输入、event、audit、checkpoint、evidence 和报告 MUST 排除凭据、MCP URL secret、完整未筛选工具 payload 和模型密钥。结构化运行日志只能记录 task/job/tool 名、参数键、状态和耗时，不得记录 query、完整参数值、原始日志全文、prompt 或模型输出。单元测试 MAY 注入 fake provider/MCP 边界，但 fake 结果 MUST 明确是测试 fixture，不能在生产 factory、fallback 或产品报告中生成。

#### Scenario: 工具错误包含 secret
- **WHEN** fake MCP 或模型异常文本包含当前配置凭据
- **THEN** 持久 failureReason、event、audit 和 API/SSE 错误均替换为 `[redacted]`

#### Scenario: 普通启动无外部调用
- **WHEN** import 诊断模块或启动未创建任务的 FastAPI app
- **THEN** 不发现 MCP、不调用 Qwen/knowledge、不执行图，也不生成任何诊断证据

### Requirement: 执行结果结构化交付给 Replanner

Executor SHALL 在计划执行完毕后产出一份结构化的执行结果，由代码依据真实调用记录组装，MUST NOT 由模型撰写或总结。执行结果 MUST 覆盖：

- 本轮计划的每一步：工具名、该步实际使用的参数、是否执行、执行顺序。
- 每一步的尝试情况：尝试次数、每次失败的原因摘要，以及该次失败属于"原样重试 / 修正后重试 / 不可重试"中的哪一类。
- 每一步的成功产出：真实返回的安全摘要，MUST NOT 使用与真实结果无关的固定占位文本。
- 产出的证据：按证据类型分组，并标明由哪一步产出。

**执行结果必须结构完整。** 无论执行结果如何——包括所有步骤都失败、没有任何可用证据——Executor MUST 为计划中的每一步产出一条记录，MUST NOT 以"提前中止"的方式交出一份不完整的执行结果。Replanner SHALL 以该执行结果与已持久化证据为唯一判断依据，并据此判定报告可信度。

执行结果中 MUST NOT 出现凭据、Region、TopicId 或其他敏感参数值。

#### Scenario: 全部步骤成功

- **WHEN** 计划的所有步骤都真实成功并产出证据
- **THEN** 执行结果为每一步记录真实参数、成功尝试次数与真实产出摘要，并按类型汇总产出的证据及其来源步骤

#### Scenario: 某一步达到尝试上限

- **WHEN** 某个步骤在尝试上限内仍未成功，且其后仍有未执行的步骤
- **THEN** 执行结果记录该步的尝试次数、每次的失败原因与失败类别，并继续为后续每一步产出记录

#### Scenario: 不可重试错误

- **WHEN** 某个步骤的失败被判定为不可重试
- **THEN** 执行结果记录一次尝试、错误类型和"不可重试"标记，该步不产生第二次调用

#### Scenario: 全部步骤失败

- **WHEN** 计划中的每一步都失败且没有任何可用证据
- **THEN** 执行结果仍覆盖计划的每一步（含未产出证据的标注），并作为 Replanner 判定证据不足的唯一依据

#### Scenario: 执行结果不含敏感值

- **WHEN** 执行结果被交给 Replanner 或写入持久事件
- **THEN** 其中不出现凭据、Region、TopicId 或其他敏感参数的具体取值

### Requirement: 证据充分性以真实日志命中为锚点

系统 SHALL 以"本轮是否拿到真实 `log_hit` 证据"作为证据充分性的唯一锚点，MUST NOT 把当前数据源无法提供的证据形态或数量组合写成必要条件。判据只保留三档：

1. **执行失败**：必需的日志检索真实失败（且不是"空结果"）并且没有任何日志命中。
2. **证据不足**：一条真实日志命中都没有。
3. **证据充分**：拿到了至少一条真实日志命中。

删除"需要时序时必须存在日志上下文证据"与"多源组合（若干条命中同时要有指标）"这类要求。日志上下文的顺序信息在当前数据源由检索结果自身携带，因此不得再要求一个独立工具产物；指标只有在数据源真实提供时才参与判断，MUST NOT 作为必要条件。

判据 MUST 由真实持久化的证据与步骤记录计算，MUST NOT 取决于模型自述。

#### Scenario: 单条真实日志命中即视为证据充分

- **WHEN** 本轮只拿到一条真实 `log_hit`，没有指标、也没有日志上下文产物
- **THEN** 证据状态为 `verified_evidence`，不得因为"命中数量不足"或"缺少指标"判为不足

#### Scenario: 完全没有命中才是证据不足

- **WHEN** 本轮没有任何 `log_hit`
- **THEN** 证据状态为 `insufficient_evidence`，并标注缺失的能力是日志检索

#### Scenario: 日志检索真实失败且无命中

- **WHEN** 必需的日志检索失败（错误分类不是空结果）并且没有任何命中
- **THEN** 证据状态为 `execution_failed`

#### Scenario: 空结果不算执行失败

- **WHEN** 日志检索正常执行但返回空结果，且后续扩宽查询仍未命中
- **THEN** 证据状态为 `insufficient_evidence`，而不是 `execution_failed`

