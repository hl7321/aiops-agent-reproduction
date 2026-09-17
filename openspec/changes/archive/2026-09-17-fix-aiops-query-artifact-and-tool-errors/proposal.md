# 修复生成的查询转义与工具失败可见性

## Why

诊断只要走到 `SearchLog` 就必失败，且失败原因在系统里看不到。

根因有两层：

1. **查询被双重转义。** `TextToSearchLogQuery` 的返回是一段嵌在 JSON 里的转义文本，中间的产物 adapter 用正则取出 `sql` 代码块后**没有反转义**，于是字面量 `\n`、`\"` 被原样送进 SearchLog。CLS 把 `\nservice` 解析成字段名 `nservice`，返回 `SyntaxError [field: nservice, can not search on this field]`；MCP 把它包成执行错误，诊断侧只看到 `transport`，三次 attempt 全失败，随后重规划又因计划不合法而终止任务。
2. **失败原因被丢弃。** 工具失败分类目前只保留异常类型名（`transport: _MCPToolExecutionError`），把服务端返回的原话丢掉了，因此上面那条语法错误在系统里完全不可见，只能靠外部工具反复反推。

这解释了此前"重跑就好了"的假象：成功的那次走的是服务端自拼的兜底查询（无转义），失败的那次走的是模型生成、经 adapter 提取的查询（带转义）。

## What Changes

- query-builder 的中间产物 adapter 在提取生成结果后 MUST 还原转义，产出可直接执行的 CQL；不得把 JSON 转义序列带进 SearchLog 参数。
- 工具失败分类 MUST 在脱敏前提下保留一段服务端返回消息，使语法错误、权限错误、字段错误在 step、事件与审计里可见。
- 新增脚本级与单元级测试：转义还原、脱敏后的失败消息可见、原有重试与路由行为不回归。

非目标：

- 不改 attempt 上限、退避策略与 retry/replan/permanent 的路由判定。
- 不改 Region/TopicId 等服务端权威参数的处理方式。
- 不修复日志定位字段（`PkgId`/`PkgLogId`）缺失问题，另立变更处理。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: query-builder 中间产物必须还原为可执行查询；工具失败分类必须在脱敏前提下保留服务端消息。

## Impact

- 影响的模块：`apps/backend/src/super_ai/aiops`（`cls_tool_adapters` 的查询提取、`tool_failures` 的失败分类）。
- 影响的接口：无 HTTP/SSE 形状变更；`tool.call` 事件与 step 的 `error_message` 内容更具体。
- 依赖：无新增依赖。
- 风险：低到中。错误消息进入持久化与事件流，必须确认脱敏充分，不能带出凭据、Region、TopicId。
