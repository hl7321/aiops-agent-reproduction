## Why

P20–P22 已提供真实告警、durable 诊断、持久 SSE、证据链与诊断 case，但 `/aiops` 仍是占位页。现在需要把这些已稳定边界组合为专业中文桌面控制台，让值班人员能够从真实输入发起诊断、观察执行、恢复状态并追溯报告与案例。

## What Changes

- 用真实 `/aiops` 三栏工作区替换 AIOps 占位页，并固定在 workspace 可用高度内独立滚动。
- 新增 typed `aiopsClient` 与 Pinia store，消费真实告警、诊断、background job、持久 SSE、证据链和 case API。
- 支持手工 query、可选告警预填/创建、历史切换、任务取消、断流后 REST 对账恢复。
- 用可读 timeline 表达 phase、工具生命周期、证据和重规划；不新增私有状态或 raw JSON 产品界面。
- 使用 marked + DOMPurify 安全渲染报告，并提供 owner 知识文档导航和可追溯 case 详情。
- 不新增后端 endpoint；把已有创建合同收窄为“query 或 alert 至少一项”，从而支持无告警的手工诊断；不自动重订阅断开的 SSE，不伪造告警、历史、日志、工具结果或诊断结论。

## Capabilities

### New Capabilities

- `final-aiops-workspace`: 最终桌面 AIOps 控制台的数据流、三栏布局、持久恢复、timeline、报告、证据与 case 交互。

### Modified Capabilities

- `chinese-vue-app-shell`: `/aiops` 从明确占位升级为连接真实后端的完整业务画布。
- `api-and-sse-contracts`: 诊断创建允许空 alerts，但 query 与 alerts 不得同时为空。
- `aiops-diagnosis-and-evidence`: 手工 query 可独立创建诊断，真实告警快照仍为可选有界输入。

## Impact

影响 `apps/frontend` 的 router、client、Pinia store、组件、视图与测试，及创建诊断的 TypeScript/Pydantic 校验与对应 OpenSpec 主规格；复用现有 endpoint、公共 ApiClient/SseClient、认证清理机制和知识页 query 定位，不增加后端迁移或外部依赖。
