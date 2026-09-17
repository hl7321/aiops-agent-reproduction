# 修复诊断证据引用契约漂移

## Why

AIOps 诊断的实时流会在发出 `reference.source` 事件时被前端判为非法，导致 SSE 断开，用户看到"SSE 数据不符合共享事件合同，请手动重新订阅或取消后台任务"。

根因是共享契约内部自相矛盾：`DiagnosticEvidenceKind` 定义了 7 种诊断证据种类，但 `reference.source` 在 `aiops` 频道下的运行时校验把种类硬编码成 4 种。后端按完整定义发送证据，其中 `log_hit`、`log_context`、`query_artifact` 三类会被 guard 拒绝。

该缺陷自 2026-08-21 引入 AIOps 诊断能力起即存在：它只破坏实时显示、不影响后台任务与持久化结果，因此长期未被发现；直到演示环境补齐真实日志与真实告警、诊断能够推进到产生日志类证据时才暴露。

## What Changes

- 共享契约中的诊断证据种类收敛为**单一运行时事实来源**：导出一份常量清单，TypeScript 类型由该清单派生，SSE 校验函数引用同一清单，消除"类型 7 种、校验 4 种"的双份维护。
- `reference.source` 在 `aiops` 频道下的校验覆盖全部诊断证据种类；未知种类仍然必须被拒绝。
- 新增契约测试：遍历全部合法种类断言通过，并断言非法种类被拒。
- 新增后端合同测试：每种 `EvidenceKind` 生成的证据引用形状都能通过共享契约。
- 新增前端 store 测试：收到全部合法种类时不会进入断流分支。

非目标：

- 不修改 SSE 事件目录、公共字段、`tool.call` 生命周期或 `task.status` 语义。
- 不修改"断流后不自动重新订阅"的前端行为。
- 不修复日志定位字段（`PkgId`/`PkgLogId`）缺失问题，另立变更处理。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `api-and-sse-contracts`: `reference.source` 在 `aiops` 频道下的证据种类校验必须与 `DiagnosticEvidenceKind` 同源并覆盖全部种类；跨语言合同测试必须覆盖该形状。

## Impact

- 影响的包：`packages/api-contracts`（类型与运行时 guard）、`apps/frontend`（SSE 消费与 store 测试）、`apps/backend`（仅新增合同测试用例）。
- 影响的接口：`POST /aiops/diagnostics/{id}:stream` 的事件形状（行为修正，形状本身不变）。
- 依赖：无新增依赖。
- 风险：低。生产代码只改契约常量与 guard；后端不修改生产逻辑。
