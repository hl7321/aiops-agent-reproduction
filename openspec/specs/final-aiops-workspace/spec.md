# final-aiops-workspace Specification

## Purpose

本能力把真实告警、持久诊断、执行事件、证据链、报告与诊断案例组合为一个专业中文桌面控制台，使值班人员能够在不依赖临时前端状态或虚假数据的前提下完成诊断操作与追溯。

## Requirements

### Requirement: AIOps 使用固定三栏桌面工作区
`/aiops` SHALL 在 workspace 可用高度内提供三栏布局：左栏显示诊断输入、活跃告警与历史，中栏显示当前报告与实时 timeline，右栏显示证据/执行链与案例库。整页 MUST 隐藏外层溢出，每栏和长 Markdown 报告 MUST 在自身有界区域独立滚动；右栏 provenance 不得被报告长度挤出页面。当前验收只面向桌面浏览器，不新增移动替代流程。

#### Scenario: 长内容保持栏内滚动
- **WHEN** 历史、报告、证据或案例内容超过可用高度
- **THEN** 对应栏独立滚动且三栏高度保持固定，报告不撑高 workspace 页面

#### Scenario: 桌面三栏信息分工
- **WHEN** 已认证用户进入 `/aiops`
- **THEN** 左中右三栏分别呈现输入/历史、报告/timeline、证据/案例且不存在嵌套的 Chat 会话栏

### Requirement: 输入和告警只消费真实来源
用户 SHALL 能提交有界手工 query，并可选择零或一条当前真实 ActiveAlert 创建诊断；页面 SHALL 支持刷新真实告警、从选中告警预填 query，并把选中告警作为创建请求的 alerts。当前合同没有独立 context 字段，前端 MUST NOT 发送该字段或构造默认告警。告警获取失败 MUST 显示安全错误，不得显示静态告警替代。

#### Scenario: 手工 query 创建
- **WHEN** 用户输入 query 且没有选择告警
- **THEN** 页面使用当前合同创建诊断且不发送 context 或伪造 alert

#### Scenario: 告警预填并创建
- **WHEN** 用户刷新并选择一条真实告警
- **THEN** query 得到可编辑预填，创建请求包含该原始标准告警快照

#### Scenario: 告警来源失败
- **WHEN** 活跃告警 API 返回全源不可用错误
- **THEN** 页面显示失败状态和重试入口且告警列表保持真实空状态

### Requirement: Pinia 以服务器和持久任务为事实来源
typed client/store SHALL 管理 history、activeAlerts、cases、activeTask、activeBackgroundJob、liveEvents 与 evidenceChain；所有领域数据只保存在内存并通过真实 REST/SSE 获取。创建后 SHALL 订阅关联诊断的持久 SSE；流断开后 SHALL 重新读取任务详情、历史、证据链与 cases 对账恢复，但 MUST NOT 自动重新订阅 SSE。用户可通过 background job id 取消 queued/running job。

#### Scenario: 创建后消费持久流
- **WHEN** 创建 API 返回 accepted task 和 queued backgroundJob
- **THEN** store 保存两种状态并从该 task 的 stream 按 sequence 消费共享事件

#### Scenario: 断流后持久恢复
- **WHEN** SSE 在 complete 前断开或解析失败
- **THEN** store 标记流已断开，调用 REST 刷新详情、history、evidence chain 与 cases，且等待用户操作而不自动重新订阅

#### Scenario: 取消持久任务
- **WHEN** 当前 background job 为 queued 或 running 且用户确认取消
- **THEN** 页面调用通用 cancel API，并对账诊断与 job 状态而不创建诊断专用取消协议

#### Scenario: 认证清理
- **WHEN** logout、认证失效或共享 401 清理发生
- **THEN** AIOps store 清空全部历史、事件、证据和 case 内存状态且不删除服务端数据

### Requirement: 状态与 timeline 保持合同语义
页面 MUST 分开显示 diagnostic 的 `accepted|running|succeeded|failed|cancelled` 与 background job 的 `queued|running|succeeded|failed|cancelled`。Planner、Executor、Replanner 与 Report SHALL 作为 timeline phase 派生展示，禁止扩充为领域状态或私有 SSE type。timeline SHALL 展示 typed task progress、tool lifecycle、reference evidence、report 与 terminal 事件；工具失败和 provider error 不得显示为成功。

#### Scenario: phase 不是状态
- **WHEN** task.status message 表示规划、执行或重规划进度
- **THEN** timeline 显示对应 phase 文案，同时状态徽标仍只使用共享 diagnostic/job lifecycle

#### Scenario: 工具失败保持失败
- **WHEN** 收到 failed tool.call 或共享 error event
- **THEN** timeline 和任务摘要显示失败信息，且不会生成 succeeded、报告或假工具结果

#### Scenario: 工具输出安全折叠
- **WHEN** timeline 展示 completed/failed 工具调用
- **THEN** 默认只显示可读安全摘要并折叠详情，不直接渲染 raw JSON 或完整参数/输出

### Requirement: 报告和证据保持安全 provenance
报告 SHALL 使用 marked 与 DOMPurify 安全渲染，不可信 raw HTML MUST 被禁用或清洗。固定中文报告结构、fallback 与不确定性标记 MUST 保持可见；证据链 SHALL 用结构化 evidence、report links 与 tool audits 展示来源关系，不以 raw JSON 充当产品 UI。

#### Scenario: 安全渲染长报告
- **WHEN** report Markdown 包含长代码块、链接或不可信 HTML
- **THEN** 页面在中栏内部安全渲染且脚本/危险 URL 不可执行

#### Scenario: 查看执行与证据链
- **WHEN** 当前诊断已有 steps、evidence、report links 与 audits
- **THEN** 右栏按可读字段显示其关联、来源和状态，不打印 JSON.stringify 结果

#### Scenario: fallback 和不确定性
- **WHEN** 报告 generationMode 为 fallback 或 uncertainty 为 true
- **THEN** 页面显示明确中文提示且不把内容包装成确定性成功结论

### Requirement: 案例库连接 owner 知识文档
案例库 SHALL 从真实 case list/detail 合同展示 alertName、service、summary、rootCause、remediation、evidenceIds 与来源标识，并提供导航到 `/knowledge` 对应 owner `knowledgeBaseId/documentId` 的操作。前端 MUST NOT 构造假 case 或把 case 当作本地历史。

#### Scenario: 查看结构化 case
- **WHEN** owner 选择一个真实 case
- **THEN** 右栏显示其结构化字段和 source task/report/evidence provenance

#### Scenario: 打开 case 文档
- **WHEN** 用户点击打开知识文档
- **THEN** 路由导航到 `/knowledge` 并携带服务器返回 documentId 及当前 owner 默认知识库 id，使知识页选中对应文档

#### Scenario: case 刷新对账
- **WHEN** 诊断完成或断流恢复后刷新 cases
- **THEN** 页面只展示服务器当前返回的 owner-scoped case 列表

### Requirement: AIOps 步骤与报告接入持久反馈

AIOps 工作区 SHALL 为真实持久化 diagnostic step 和 diagnostic report 分别展示 `UserFeedbackControl`，以 step id 或 report id 作为无 subject 的 target。重新打开诊断或从断流恢复持久状态时 SHALL 从反馈 API 恢复对应记录；timeline 中非 step 的 plan、tool event、evidence 或临时状态不得伪装成可反馈 step。

#### Scenario: 步骤和报告分别恢复

- **WHEN** 用户重新打开包含步骤和最终报告的诊断
- **THEN** 各 diagnostic step 恢复自己的反馈
- **AND** diagnostic report 恢复独立反馈

#### Scenario: 非目标 timeline 项不提供反馈

- **WHEN** timeline 展示 plan、tool lifecycle、evidence 或 task status
- **THEN** 这些项目不显示 diagnostic_step 反馈控件

#### Scenario: AIOps 反馈失败保持可重试

- **WHEN** step 或 report 的反馈更新/删除失败
- **THEN** UI 保持服务器已保存状态与本地待重试输入
- **AND** 不将 provider 或网络失败显示为成功
