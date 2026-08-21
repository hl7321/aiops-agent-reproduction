## Context

见 `proposal.md`。当前 `/aiops` 仍由 `PlaceholderView` 渲染，但 P20–P22 已提供 typed contracts 与真实 API：活跃告警、诊断创建/列表/详情/证据链/持久 SSE、通用 background job 取消、case 列表/详情。前端已有公共 `ApiClient`、`SseClient`、认证清理注册、安全 Markdown 渲染和知识页 query 定位，可直接复用。

## Goals / Non-Goals

**Goals:**

- 用模块化 Vue 组件组合最终桌面三栏 AIOps 工作区。
- 保持 REST、SSE、diagnostic、background job 与 timeline phase 的语义边界。
- 断流时以持久 REST 状态恢复，不隐式扩展重连协议。
- 报告、工具摘要、证据和案例以安全、可读、可追溯方式呈现。

**Non-Goals:**

- 不新增后端 endpoint、数据库或 SSE union；只修正现有创建请求“query 或 alerts 至少一项”的校验。
- 不实现自动 SSE 重订阅、移动端替代布局、诊断专用 cancel/retry。
- 不显示 raw JSON、完整工具参数/输出或任何 fake 产品数据。

## Decisions

### 1. client、store、展示组件三层分离

`aiopsClient` 只负责共享合同对应的 HTTP/SSE 调用；`aiopsStore` 管理服务器快照、active selection、流消费和恢复编排；`AiopsView` 与子组件只呈现和触发 store action。备选的单文件页面会把 transport、状态机和布局耦合，难以稳定测试断流与清理，因此拒绝。

### 2. 一个 store 保存两套权威 lifecycle

active detail 同时保留 `DiagnosticTask.status` 与 `BackgroundJob.status`，UI 用两个明确标签展示。Planner/Executor/Replanner/Report 仅由 typed `task.status.data.message`、tool/reference/report event 推导 timeline phase，不进入 lifecycle union。这样不会把前端显示概念写回产品合同。

### 3. SSE 断开执行一次 REST 对账，不自动重订阅

store 通过公共 `SseClient` 按 sequence 顺序消费；正常 `complete` 后刷新 detail/history/evidence/cases。若迭代抛错或流无 complete 结束，则记录 `streamDisconnected=true` 并执行相同 REST 对账，但不再次调用 stream。用户可通过“重新查看实时进度”显式订阅当前非终态任务；这不虚构自动重连。

### 4. timeline 使用安全 view model

store 把共享事件映射为 `AiopsTimelineItem`：phase、status、title、summary、timestamp、可选安全 detail。tool.call 仅使用合同提供的 toolName/lifecycle/summary，reference 使用结构化字段，error 使用共享安全 message；组件禁止 `JSON.stringify`。持久 detail 的 steps/audits/evidence 用独立列表补充执行链，不伪造 SSE 历史。

### 5. 报告与案例复用既有安全/导航边界

报告复用 `renderSafeMarkdown`，中栏 `.aiops-report-scroll` 独立滚动。case 合同没有 knowledgeBaseId，因此打开文档时先读取当前 owner 默认知识库（复用 knowledge client 或稳定默认列表结果），再导航 `/knowledge?knowledgeBaseId=...&documentId=...`。不从 case id 推导 KB，也不新增合同字段。

### 6. 页面初始化和 protected cleanup

进入 `/aiops` 并行读取 alerts、history、cases；选择历史后读取 detail/evidence。store 注册到 protected store registry，清理时中断本地消费标识并清空全部内存数据，但不删除服务端资源。所有请求继续通过公共 ApiClient 注入 bearer 和处理 401。

### 7. 手工 query 与可选告警使用同一创建合同

现有 endpoint 和 payload 字段保持不变，但将 Pydantic 的 `alerts min_length=1` 改为 `alerts` 默认空列表，并在模型级校验 `query` 去空白后与 alerts 至少存在一项；两者均空时返回共享 validation error。前端始终发送真实 `alerts` 数组（未选告警时为 `[]`），不新增不存在的 `context` 字段。这样既满足手工诊断，也不允许创建无输入任务。

## Risks / Trade-offs

- [断流后页面不自动恢复实时推送] → 明确显示已断开、完成 REST 对账并提供显式重新订阅按钮。
- [三个 endpoint 对账存在短暂时间差] → 以每个响应的服务器状态分别展示，不尝试构造跨 API 原子快照。
- [timeline message 文案不能可靠解析所有 phase] → 使用保守关键词映射，无法识别时归为“任务进度”，绝不产生新领域状态。
- [case 没有 knowledgeBaseId] → 运行时读取 owner 默认知识库，不在浏览器猜测 tenant 或 KB id。

## Migration Plan

1. 先增加创建合同边界测试，修正 query/alerts 校验，再增加 client/store 失败测试并实现真实 transport、恢复和取消。
2. 增加三栏组件与视图测试，替换 router 占位组件。
3. 运行前端/contracts/相关后端与 OpenSpec 门禁；环境完整时执行桌面真实链路 smoke。
4. 回滚时恢复 `/aiops` 路由组件即可，不影响任何服务端持久数据。
