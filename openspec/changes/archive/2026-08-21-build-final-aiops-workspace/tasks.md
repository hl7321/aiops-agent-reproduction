## 1. Typed transport 与 store

- [x] 1.0 先增加创建诊断输入测试，再把共享合同修正为 query 或 alerts 至少一项，保持 endpoint 和字段不变。
- [x] 1.1 先增加 `aiopsClient` 失败测试，再实现 alerts、diagnostics、detail、evidence、cases、background cancel 与持久 SSE 的共享合同调用。
- [x] 1.2 先增加 store 初始化/选择/创建测试，再实现 history、activeAlerts、cases、active task/job、events 与 evidence chain 的服务器对账。
- [x] 1.3 先测试 SSE complete、异常断流和显式重新订阅，再实现顺序消费、正常完成刷新、断流 REST 恢复且不自动重订阅。
- [x] 1.4 先测试 queued/running cancel、失败状态与 protected cleanup，再实现通用 background job 取消和认证清理。

## 2. 可读 timeline、报告与 provenance

- [x] 2.1 先测试 phase 映射、tool/reference/error/report event，再实现不扩充 lifecycle 的 typed timeline view model。
- [x] 2.2 先测试工具摘要默认折叠与禁止 raw JSON，再实现 execution/timeline 组件和持久 steps/audits/evidence 补充视图。
- [x] 2.3 先测试危险 HTML、长 Markdown、fallback/uncertainty，再实现报告安全渲染与栏内滚动。
- [x] 2.4 先测试 case 结构化详情、刷新和知识文档 route query，再实现 case 库与 owner 默认知识库导航。

## 3. 三栏工作区与交互

- [x] 3.1 先测试手工 query、真实告警刷新/选择/预填和无 context 字段，再实现左栏输入、告警与历史组件。
- [x] 3.2 先测试 diagnostic/job 双状态、create、cancel、失败和断流提示，再实现中栏报告/timeline 控制。
- [x] 3.3 先测试证据/执行链/case 交互和可访问文字，再实现右栏 provenance 组件。
- [x] 3.4 用真实 `AiopsView` 替换 router 占位页并测试固定三栏、各栏独立滚动、长内容不撑页和不显示 raw JSON。

## 4. 验证、同步与归档

- [x] 4.1 运行 frontend typecheck/test/build、contracts typecheck/test 与相关 backend tests，修复全部问题。
- [x] 4.2 运行 `openspec validate --all`、`git diff --check`；真实联合环境缺少运行中的 Compose/应用、CLS MCP URL 与 AIOps demo 登录配置，因此桌面 smoke 如实记录为未执行。
- [x] 4.3 使用 `$openspec-verify-change` 核对完整性、正确性与设计一致性，修复所有 CRITICAL/WARNING。
