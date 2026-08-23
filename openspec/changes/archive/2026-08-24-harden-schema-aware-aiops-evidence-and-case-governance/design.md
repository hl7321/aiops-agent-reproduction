## Context

现有 P21 运行时先做 owner-scoped SOP 检索，再把 `knowledge_retrieval` 与当前 owner enabled MCP connections 的全部真实工具放入 request-local registry。Planner 只收到工具名称并被要求恰好规划一个 SearchLog；`validate_plan` 不验证每步参数或工具依赖。Executor 只为 SearchLog 使用 runtime JSON Schema 做有限参数收敛，其他工具参数直接交给 LangChain MCP adapter；工具输出则依靠名称包含 `searchlog|metric|knowledge` 推断证据类型。

官方 CLS MCP 同时提供二十余个工具。其说明要求先以 TextToSearchLogQuery 产生 CQL，SearchLog 原始结果再提供 Time/PkgId/PkgLogId 给 DescribeLogContext。当前宽发现、弱规划、窄证据适配三者不一致，DescribeLogContext 即使调用成功也无法进入现有 evidence kind。P21 report fallback 仍可把 task 转为 succeeded，P22 report 节点随后自动生成 case；同 task 和同文档已有幂等约束，但不同 task 的相同故障会因随机来源 ID 改变 Markdown/hash 而形成重复知识。

本 change 延续项目本地优先配置边界：`clsLogUpload.region/topicId` 继续来自 project.json 与 user.project.json 深合并结果，作为单一 CLS 演示/诊断目标。本次不解决多地域、多 Topic 或远端配置中心。

## Goals / Non-Goals

**Goals:**

- 在动态 MCP 安全白名单上叠加 AIOps 只读取证能力白名单。
- 让 Planner 基于能力、描述、Schema 和依赖生成可验证计划。
- 对全部允许工具执行输入验证，对证据/辅助工具执行显式输出适配；核心 CLS 工具使用 Pydantic 模型和确定性跨步参数传递。
- 使校验/调用失败可分类、最多三次纠错并完整持久化。
- 按查询来源和 claim 建立条件证据门禁，不以固定工具数量替代证据充分性。
- 取消 report 完成时自动知识沉淀，改为反馈审批后的显式提升。
- 用 canonical fingerprint 和规范化来源关系阻止跨任务重复向量污染。

**Non-Goals:**

- 不修改 Region/TopicId 的本地 JSON 来源，不增加日志源注册表、自动 Topic 发现或远端部署映射。
- 不支持任意 MCP 工具由模型自动推断证据 Schema；未登记工具默认不可用于 AIOps。
- 不让模型执行修复、写配置、修改告警或其他有副作用的 MCP 工具。
- 不做自动语义合并；相似案例必须由用户决定。
- 不改变 durable worker 的 lease、heartbeat、retry job 或 checkpoint 基础语义。

## Decisions

### 1. 两层白名单而不是固定三工具或全部放行

第一层 `discovered registry` 继续由 owner enabled MCP connections 每轮真实发现生成，负责存在性、owner 和重名安全。第二层 `AiopsToolPolicy` 只登记诊断允许的只读能力，运行时取交集后才交给 Planner。核心策略项包含 tool name、capability、readOnly、evidenceKind、dependencies、requiredForProfile、input/output adapter 和 retry policy。

选择该方案是因为固定三个名称会阻断未来合法 metric 能力，而全部动态工具会把告警管理、主题管理等非取证工具暴露给 Planner。未登记工具默认拒绝，新增能力必须显式增加 adapter 与测试。

### 2. CLS Profile 使用条件能力图而不是固定三工具链

Planner 仍由 Qwen structured output 生成有界计划，但输入从名称列表升级为有界 catalog。当前 Profile 继续继承 P21 的“恰好一个真实 SearchLog”，其余能力由条件边决定：

```text
可信服务端 Query ─────────────────────┐
                                      ▼
自然语言 Query ── TextToSearchLogQuery ── SearchLog ── log hit
                                                   │
                           claim 需要时序 + 有定位字段？
                                  │是                    │否
                                  ▼                      ▼
                         DescribeLogContext       评估其他真实证据
                                  └──────────┬───────────┘
                                             ▼
                                  claim evidence policy
```

SearchLog 是当前 Profile 必需运行证据。TextToSearchLogQuery 仅在 Query 未经服务端可信生成/校验时必需。DescribeLogContext 仅在结论需要调用顺序、重试、熔断或恢复等时序证据且命中包含定位字段时必需；若 claim 不依赖时序，或多个 log hit 与独立 metric 等已满足 policy，则不强制调用。需要上下文时 SearchLog 必须请求原始日志，不允许 SQL AnalysisRecords 作为入口。

相比完全硬编码流水线，该方案保留 Planner 对可选步骤和证据策略的判断；相比自由 Agent，条件边、权威参数和最终 claim gate 仍由服务器验证。DescribeLogContext 失败时 Replanner 可以选择其他已登记证据工具，但不能把缺失上下文伪造成成功；最终不足则只产生 `insufficient_evidence`，不可提升知识。

### 3. 所有允许工具输入可验证，所有产物显式适配

新增独立工具 policy/adapter 边界。每个允许工具至少提供：

- runtime MCP JSON Schema 兼容性检查；
- runtime input validator；
- MCP content/structured content 解包；
- 受信任参数覆盖规则；
- evidence 或辅助产物 adapter；
- retry classifier。

核心 CLS 三工具额外使用显式 Pydantic input/output model：`TextToSearchLogQuery` 产生非证据 query artifact；`SearchLog` 产生 `log_hit`；`DescribeLogContext` 产生 `log_context`。SearchLog 的 Region/TopicId 由现有本地配置覆盖，DescribeLogContext 的 Region/TopicId 使用同一配置，Time/PkgId/PkgLogId 使用已验证命中覆盖。模型只能修正 Query、时间范围或有界可选项。QueryMetric 等其他允许工具必须有自己的模型/adapter，禁止强行复用日志形状。

选择“runtime Schema 输入校验 + 已登记业务 adapter”而不是从任意 JSON Schema 动态猜测证据，是因为 JSON Schema 只能描述形状，不能表达“该结果是否是运行证据”“PkgId 来自哪一步”以及 MCP wrapper 的业务语义。runtime Schema 用于所有允许工具的输入兼容性，证据工具必须再经过本地输出 adapter；官方升级导致不兼容时 readiness/任务明确失败。

### 4. attempt 是步骤内规范化生命周期

`diagnostic_steps` 从“一计划位置一条 attempt=1 记录”扩展为同 planVersion/position 下最多三次 attempt。Pydantic 只产生结构化 validation details，独立 classifier 决定处理：模型可修正的输入错误进入 corrective retry；空结果进入 Replanner query refinement；timeout、429、临时 5xx 使用有界退避；配置缺失、401/403、owner 越权、未允许工具、Schema 不兼容和永久 4xx 不重试。输出验证错误只有在 runtime Schema 仍兼容且错误可能是瞬时响应时才允许有界重试。

每次 attempt 独立 audit/event/checkpoint。纠错模型不接收凭据、完整日志或权威字段的值，返回后仍由服务端 adapter 校验和覆盖。进程重启根据 checkpoint 找到最后完成 attempt，既不重复成功调用，也不会把 failed attempt 当成已完成步骤。

durable worker 恢复时读取同一 planVersion/position 已持久化的最大 attempt，并从下一编号继续，而不是重新使用 attempt=1。遗留在 running 的 attempt 先以安全的中断分类收口；每次失败均保存 checkpoint。必需 SearchLog 已耗尽三次后进入 Replanner 形成失败说明，但 report 节点最终抛出统一错误，使 diagnostic/background job 均落为 failed，而不是把失败说明包装成 succeeded。

### 5. 证据充分性按 Profile 与 claim 评估

Replanner 的输入增加结构化 attempt/error/missingCapabilities 和待支持 claim。SearchLog、配置、授权、Schema 兼容性等当前 Profile 或 runtime 永久失败进入 `execution_failed`。DescribeLogContext 等条件能力失败后，Replanner 可以选择其他已登记只读工具；evidence evaluator 最终逐 claim 判断是否满足 policy。满足时报告可为 `verified_evidence`，不满足时只能为 `insufficient_evidence`，两者均不得靠工具数量或 Prompt 自述决定。

这有意修改旧的“有任意非 alert 证据即可在重规划上限后 fallback succeeded”行为。`insufficient_evidence` 表示工作流完成但无法确认根因，不得显示为可信结论、不得提升知识；`execution_failed` 表示运行或永久依赖错误。为避免同时扩张 durable job 和 diagnostic status 状态机，本 change 使用 report trustState 与明确 failureCode 区分结果，不新增另一套 SSE 私有状态。

### 6. 报告信任状态与 case 提升分离

`diagnostic_reports` 增加 trust state。report 节点只负责保存报告和 provenance，不再调用 `DiagnosisCasePersistor`。新的显式 promote service 在事务中重新读取 owner report、positive diagnostic_report feedback、uncertainty 和 evidence links；全部满足后才进入 case 创建。

feedback POST 仍只是评价，不自动产生知识写入，避免一次点赞立刻触发难察觉的外部状态变化。前端以单独按钮发起 promote。已有 legacy save-to-knowledge 路由需要迁移为相同可信门禁，不能继续绕过审批直接制造不确定知识。

### 7. 精确 fingerprint 自动去重，语义相似人工决策

canonical case 使用两个稳定摘要：

- `incidentFingerprint`：owner scope 下对规范化 service、alertName、dependency、rootCause 和 remediation 生成版本化 SHA-256；
- `knowledgeFingerprint`：对最终 canonical Markdown 的业务字段生成 SHA-256，排除 task/report/evidence/document 随机 ID 和时间戳。

数据库以 owner + fingerprint 建立唯一约束。`diagnostic_case_sources` 保存多个 task/report/approval feedback/evidence IDs 对 canonical case 的来源。精确重复只追加 source。语义相似通过现有 owner-scoped retrieval 生成候选，但不会自动写入；用户选择合并时只追加 provenance，选择新建时要求显式确认。

incident fingerprint 与 knowledge fingerprint 都是独立数据库唯一边界，任一精确命中都复用 canonical case 并追加 source。case 文档 metadata 同时保存两个带版本 fingerprint。`approval_feedback_id` 使用 nullable + `ON DELETE SET NULL`：用户仍可删除反馈且不会级联删除已创建的 case、文档或索引；之后再次提升时仍重新检查当前持久反馈。

### 8. P25 fixture 提供可验证的上下文能力

java-ecommerce 每个 incident 改为多条有序日志，并使用稳定且相互隔离的 context flow。生成仍为纯函数，SDK client 仍只在显式 CLI 后创建。自动测试验证 payload/context，不声称 CLS 可检索；真实 smoke 验证 SearchLog 返回 Time/PkgId/PkgLogId，并在需要时成功调用 DescribeLogContext。这证明上下文能力可用，不把它升级为所有生产 claim 的固定步骤。

上传 payload 为每个 incident 建立独立 CLS LogGroup，而不是把十套场景放进同一上下文组，避免 DescribeLogContext 把不同故障的相邻日志混在一起；quant profile 仍保持原单组兼容行为。

### 9. 合同和前端只展示安全结构

contracts 增加 attempt、errorCategory、report trustState、promotion result/candidate DTO。SSE 继续复用既有 union，不新增 plan/validation 私有事件；详细进度通过 typed task.status message/progress 和 tool.call 的安全 summary 表达。前端不接收 Region/TopicId、凭据、完整参数或 raw MCP response。

## Risks / Trade-offs

- [官方 CLS MCP Schema 升级导致 adapter 不兼容] → discovery 后做兼容性检查，明确失败并用脱敏 fixture 锁定当前官方形状。
- [条件证据策略可能被实现得过宽] → 用显式 Profile/claim 测试固定 SearchLog 必需、时序 claim 上下文要求和可接受替代证据；模型不能自行宣布充分。
- [模型纠错产生新的非法参数] → 最多三次且每次都重新经过服务端 adapter；权威字段不可修改。
- [fingerprint 规则升级造成重复] → fingerprint 带版本，迁移保留旧值；新版本只用于新提升，不后台重写向量。
- [相似候选判断存在误报] → 永不自动合并，用户明确选择后才写入。
- [本地单 Topic 配置限制多部署] → 接受当前 local-first 范围；未来多源需求另立 OpenSpec，不在本 change 预设计。

## Migration Plan

1. 先增加兼容 Alembic 列/表和 contracts，旧 report/case 保持可读但默认不具备新的提升资格。
2. 增加 policy/adapter/attempt 持久化与严格运行时，使用 fake MCP 和脱敏真实样本完成回归。
3. 切断 report→automatic case 调用，再启用 feedback-gated promote；现有 case/document/vector 不删除、不重写。
4. 增加 fingerprint/source，新的提升走 canonical 去重；旧 case 仅在显式访问或人工迁移时补齐，不自动合并。
5. 更新 fixture、前端和文档；执行全量门禁。真实外部 smoke 只在用户明确确认后执行。

回滚时可恢复旧应用版本读取新增 nullable/default 列，但不得恢复自动沉淀行为；若新迁移已部署，表和列保留以避免破坏 provenance。
