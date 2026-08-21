## Context

见 `proposal.md`。现有 P09 worker 以 SQLite background job/event 提供 lease、heartbeat、restart、retry、timeout 和协作取消；P12 提供 owner-scoped `knowledge_retrieval`；P18 提供 owner enabled MCP target 与真实 tool discovery；P15 的通用审计已经支持 `diagnosticTaskId` parent；P20 提供标准 ActiveAlert。当前 SSE union 已有诊断所需事件，但 task lifecycle 仍使用旧 `completed` 且没有 progress，需要在 P21 对齐最终 durable 状态。

P21 是首个跨 durable runtime、LangGraph、MCP、知识检索、模型、SQLite 和 SSE 的流程。模块 import 和普通 app 启动仍不得发现工具、读取真实配置或联网；所有 client/service 必须由 handler factory 在任务运行期显式创建。

## Goals / Non-Goals

**Goals:**

- 每个诊断是可重放、可恢复、可取消/重试且 owner-scoped 的 durable workflow。
- 真实告警、SOP、日志/指标工具结果成为规范化 evidence，报告关键结论只能引用这些记录。
- LangGraph 路径和上限在代码与 checkpoint 中都可验证，模型不能扩大工具或 tenant 权限。
- API 与 stream 使用共享 contracts/SSE，客户端断开只影响连接，不影响任务。

**Non-Goals:**

- 不实现 P22/P23 的 AIOps 前端工作区、case 或人工反馈。
- 不调用 remediation/写操作工具，不自动上传日志，不把建议标记为已执行。
- 不新增诊断专用 cancel/retry、私有 SSE event 或进程内 `create_task` 运行时。
- 不保存无限制 MCP raw payload、模型 prompt/response 或任何凭据。

## Decisions

### 1. 以一个 durable handler 驱动显式 StateGraph

使用 `langgraph.graph.StateGraph`，节点固定为 planner、executor、replanner、report；边固定为 `START→planner→executor→replanner`，replanner 用条件边选择 executor/report，report 进入 END。内存中的 `DiagnosticState` 只保存 task id、next position、route 和安全错误；job/owner 来自 durable handler context，plan version、replan count、evidence id 与最后完整节点保存在数据库并在节点边界重新读取，不把 ORM、client 或完整工具 payload 放入 state。

默认 `maxPlanSteps=8`、`maxReplans=3`，由内部 typed settings 固定并可在测试注入，当前不增加用户可修改配置。节点入口和外部调用前后均执行取消检查。图 compile 与所有 client 创建发生在 handler factory/显式执行路径，模块 import 无 I/O。

备选方案是手写 while 循环；它难以证明节点/条件边与 checkpoint 一致，也偏离用户要求的 StateGraph，因此拒绝。另一方案是由 HTTP request 直接运行图，会失去 P09 的断线和 restart 语义，也拒绝。

### 2. checkpoint 是“最后一个完整节点”的 owner-scoped 追加记录

`graph_checkpoints` 使用 task 内单调 `checkpoint_version`，保存 node、planVersion、nextStepIndex、replanCount 和有界 state JSON；evidence/steps/report 只保存其 id，恢复时通过 owner-scoped Repository 重新加载规范化记录。领域写入、语义事件和 checkpoint 使用独立短事务，并按“领域记录→事件→checkpoint”提交；恢复时同时核对最新 checkpoint、当前 plan version、已成功 step 与 evidence id，所以即使进程恰好在 checkpoint 前退出，也只会安全重做未完成节点，不会把失败或未提交调用推定为成功。retry 使用 background job 的相同 resourceType/resourceId 找回同一 task，并从最新 checkpoint 恢复；审计/证据用 step attempt 和稳定关联保持可辨别。

不直接使用 LangGraph 内置 SQLite saver：项目要求 Alembic 是 schema 唯一权威、Repository owner scope 和固定六表命名；通用 saver 的内部 schema/tenant 查询不满足这些约束。我们仍使用 StateGraph 执行语义，只把 checkpoint persistence 适配为项目自己的 Repository。

### 3. Planner 的输入装配顺序由服务端固定

planner 节点先直接通过 P12 service 调用 owner-scoped retrieval，并用 `diagnosticTaskId` 创建通用 audit；空结果记录为“无 SOP”，异常显式失败。之后通过 P18 source/service 只加载当前 owner enabled targets并真实 discover tools。SearchLog 判定采用规范化工具名：移除 `_`、`-` 和空白后 casefold 必须等于 `searchlog`，从而兼容 `SearchLog`/`search_log` 而不把任意“search”工具误当日志工具。

没有 SearchLog 时在调用 planner LLM 前使用 `SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE` 失败。模型返回结构化 `PlanDraft`，服务端再次校验 1..8 步、恰好一个 SearchLog、每个 toolName 都在 `knowledge_retrieval + 当前 discovered MCP` 注册表中。无效 draft 可在总调用上限内修正一次，仍无效则安全失败；权限从服务端 registry 得出，不相信模型携带的 owner/filter。

备选方案是让模型自行先调用工具；它无法严格证明调用顺序和“缺工具立即失败”，也容易扩大权限，因此拒绝。

### 4. Executor 每次只执行一个持久步骤，Replanner 只消费 id 指向的证据

executor 根据 `nextStepIndex` 创建 running step 与 started audit，调用实际 LangChain tool，然后把结果交给按工具类别注册的 evidence normalizer。normalizer 只保留有界、安全、可查询内容：知识引用逐条转换为 knowledge evidence；SearchLog/指标工具输出要求可解析的真实结构，截取有界记录/字段并脱敏；告警在任务创建时逐条保存为 alert evidence。无法规范化的 raw payload 不直接落库，而使步骤失败。完成/失败 audit、step、semantic job event 和 checkpoint 按“领域记录→事件→checkpoint”使用独立短事务提交，并由 checkpoint 恢复规则处理中断窗口。

replanner 的结构化决定只有 `continue|replan|report`。它收到步骤摘要和 evidence 摘要，不收到不存在的结果；replan 必须再次通过同一工具注册表和 SearchLog 唯一性校验，且递增版本/计数。工具失败可由其决定在上限内调整或以不确定报告收尾，但不能改变旧 step/audit/evidence。

备选方案是一次执行整份计划后批量保存；崩溃会丢失中间过程并破坏恢复粒度，因此拒绝。

### 5. 六张表分离生命周期、过程、证据和 provenance

- `diagnostic_tasks`：owner、query、安全 alert input、status、plan/version、replan count、failure code/message、时间戳；不增加 backgroundJobId，关联继续由 background job 的 resourceType/resourceId 建立。
- `diagnostic_steps`：owner/task、plan version、position、attempt、tool name、arguments、安全状态/摘要/错误、开始/结束时间。
- `diagnostic_evidence`：owner/task/nullable step/toolCall、kind、source、title、bounded content/summary、metadata、observedAt/createdAt；task/owner/kind/source 使用索引。
- `diagnostic_reports`：owner/task、markdown、generationMode=`model|fallback`、uncertainty、createdAt；当前每次成功运行保留一个新 revision，不覆盖旧报告。
- `report_evidence_links`：owner/task/report/evidence、claimKey、section、position；外键和 Repository 校验保证同 owner/task。
- `graph_checkpoints`：owner/task、checkpoint version、node、控制 state、createdAt，task/version 唯一。

JSON 仅用于边界明确的原始输入快照、工具 arguments、metadata 和控制 state；告警、步骤、证据、报告和 links 都有独立记录，不把完整证据链放进 task payload。所有领域服务只依赖不可变 record/Repository Protocol，SQLite adapter 位于 `super_ai.memory.extended_sqlite`。

### 6. background job event sequence 是 SSE 唯一顺序权威

扩展 P09 store 增加 owner-scoped `append_progress_event(jobId, semanticType, data)`。数据库 event 的 `type` 仍表示当时 job lifecycle，`data` 保存 `{eventType,data}` 语义载荷；stream 使用事件行的 sequence/createdAt 生成 SSE id、sequence、timestamp，避免 handler 自造第二套序号。P09 自动 queued/running/succeeded/failed/cancelled event 映射为 task.status，并在 terminal 追加恰好一次 complete 或 error；handler 的语义事件映射为 tool.call/reference.source/report/task.status。

`POST :stream` 接受 `afterSequence>=0`，先 owner-scoped 找 task 与最新关联 job，再循环读取 `list_events(after_sequence)`；无新事件时有界异步轮询，terminal 且事件耗尽后结束。断开只取消 stream generator，不触发 job cancel。

共享 `TaskLifecycle` 从旧 `completed` 对齐为 `succeeded` 并增加 `cancelled`，`TaskStatusData` 增加 nullable 0..100 progress。仓库合同测试会阻止新增 plan/step/replan type。

### 7. 报告采用结构化模型结果、严格校验和确定性 fallback

report 节点只读取同 owner/task 的告警 evidence、SOP evidence、已完成/失败步骤、最终 plan 和其他真实 evidence。模型输出 `ReportDraft(markdown, claims[])`，每个 claim 携带 claimKey/section/evidenceIds/uncertain。服务端校验所有固定标题、每条告警的编号章节、evidence id 属于当前 task，且确定性关键结论至少有一个 link；校验失败等同模型失败。

fallback 是纯函数，按固定模板逐段列出告警、真实日志/知识摘要、已执行步骤和建议。它只做摘录/组织：没有支持证据时固定写“证据不足，无法确定根因”，generationMode=`fallback` 且 uncertainty=true；不调用工具、不新建 evidence、不推导新根因。模型失败但 fallback 成功时任务可 succeeded；SearchLog 工具从未可用时在 planner 阶段失败，不进入 fallback。

备选方案是保存模型 Markdown 后用文本搜索猜 provenance；它不能可靠建立 claim→evidence 外键，因此拒绝。

### 8. API owner scope 与任务状态对账

create service 在同一事务保存 task、逐条 alert evidence 和 enqueue job，响应直接返回二者。list/detail/evidence chain 的第一个业务参数始终为 owner_user_id；task 与最新 background job 通过 `get_by_resource` 在 owner scope 内对账。handler 在开始/成功/显式失败/取消时更新 task；timeout 或 runtime cancellation 通过 handler 顶层清理路径保存安全终态，进程关闭导致的取消不写 cancelled，保留 running 等待 lease recovery。

为区分用户取消、worker timeout 与应用 shutdown，P09 `BackgroundJobContext` 增加只读 termination reason，由 worker 在取消 handler 前设置 `cancelled|timeout|shutdown`；不改变现有 lease/heartbeat/clock 行为。诊断 handler 据此更新领域状态，其他 handler 可忽略该字段。

### 9. 外部 client、脱敏和测试边界

`DiagnosticRuntimeFactory` 在 job handler 被调用时根据显式 app/config dependency 创建 retrieval、Qwen chat、MCP source/gateway 和 audit/store；import/app factory 只注册惰性 handler closure。模型/MCP异常使用已有 credential redaction 并增加通用 bounded text sanitizer；日志只记录 id/name/status/duration/argument keys。

单测可注入 fake retrieval/model/MCP/tool，但 fixture evidence 必须有明确 source，断言 production factory 不生成 fake result，fallback 只引用数据库已有 evidence。真实 smoke 要同时具备 Qwen、Milvus、已索引 SOP 和 owner enabled 官方 CLS MCP SearchLog；任一缺失即记录未执行，不能用单测替代。

## Risks / Trade-offs

- [SQLite 同时保存图事件和 checkpoint 可能增加写锁竞争] → 每节点使用短事务，外部调用在事务外执行，concurrency 继续保持 P09 默认 2。
- [工具输出结构随 MCP Server 版本变化] → normalizer 严格接受安全可识别形状，失败显式，不把未知 raw JSON 当证据。
- [模型计划或 report 结构不稳定] → Pydantic structured output、服务端二次校验和有界重试；报告仍有确定性诚实 fallback。
- [任务状态与 background job 终态短暂不一致] → handler cleanup 和 detail 对账，stream 以持久 job sequence 为传输权威。
- [report revision 在 retry 后增长] → 保留历史用于审计，detail 默认返回最新 revision，evidence-chain 返回全部 links。
- [alert input 的 rawContext 可能含部署敏感字段] → 创建时执行 allowlist/bounded sanitizer，原始“安全输入”指净化后的可追溯快照，不保存未筛选响应。

## Migration Plan

1. 先扩展 contracts/SSE lifecycle 和错误目录，再增加 Alembic 六表迁移与 Repository records/adapters。
2. 实现 graph 的纯计划校验、fallback 和 fake 边界测试，再接持久节点、P09 handler/event 与 API。
3. 注册惰性 handler，运行 fresh upgrade、backend/contracts 全门禁以及 import-safety；不在启动/测试中访问外部服务。
4. 若环境完整且用户目标已确认，人工执行一条真实 CLS MCP + Qwen 诊断 smoke；否则明确记录未执行。
5. 回滚时先停止 worker，再移除 router/handler 并 downgrade 迁移；background job/event、audit 和六表数据按迁移顺序删除，不影响聊天/知识数据。
