## Context

动机与排查证据见 `proposal.md`。这里只记录实现相关的现状与约束。

当前状态：

- `runtime.executor` 在 `is_log_context_tool` 分支里，先从证据里取最近一条带定位字段的 `log_hit`（`_latest_log_hit`）；取不到就 `raise ValueError("DescribeLogContext 缺少已验证 SearchLog 定位命中")`。
- 该异常既不是 `ToolConfigurationError`，也不属于其它专用错误，`classify_tool_failure` 因此按 `phase == "input"` 归为 `input_validation`，路由是 `retry_same_step`。
- 于是 executor 会重试三次，并在中途调用 `model.repair_tool_arguments` 让模型"修参数"——但缺的是数据，不是参数。
- `SearchLog` 命中模型 `ClsSearchLogHit` 已有 `has_context_locator` 判定，缺字段这件事在数据层是可判定的。

约束：

- 不改 `DescribeLogContext` 的必填参数，也不放宽定位字段校验。
- 不改 attempt 上限与其它失败分类。
- 已有 `log_hit` 证据必须继续有效，不能因为上下文步骤失败就丢弃它们。

## Goals / Non-Goals

**Goals:**

- 把"缺定位字段"从"可修正的输入错误"改成"数据前置条件不足"，一次说清楚。
- 让整次诊断有机会在缺少上下文的情况下仍然给出诚实报告。

**Non-Goals:**

- 不去改造日志上传路径以产出 `PkgId`（已排查，官方 SDK 无可用入口）。
- 不引入新的 SSE 事件或证据种类。

## Decisions

### 决策 1：新增专用错误类型，而不是复用现有错误

新增一个语义明确的错误（例如 `ToolContextLocatorUnavailableError`），由 `runtime` 在取不到定位字段时抛出。

理由：现有可用错误类型没有一个表达"数据不满足前置条件"。复用 `ToolConfigurationError` 会误导成"配置问题"；继续用裸 `ValueError` 就是现状。

备选方案与取舍：

- **备选：继续用 `ValueError` 但在消息里写清楚。** 分类结果不变，仍然三次重试 + 模型纠错，等于只改了文案。
- **备选：复用 `ToolEmptyResultError`。** 语义不符（这里不是"查不到"，而是"查到了但没有定位信息"），会让 Replanner 与审计记录失真。

### 决策 2：路由选择 `replan`，而不是 `permanent_failure`

分类映射为 `replan`（不可重试）：

- 该步骤本身做不了，继续重试没有意义；
- 但**整次诊断不该因此中止**——已有的 `log_hit` 与知识证据仍然有效，Replanner 可以据此缩小结论范围，必要时产出"证据不足"的诚实报告。

备选方案与取舍：

- **备选：`permanent_failure`。** 会让整次诊断以 SYSTEM_UNAVAILABLE 收场，把"这个结论做不了"错误地升级成"整次诊断失败"。
- **备选：保持 `retry_same_step`。** 就是现状，浪费三次尝试并让限制不可见。

### 决策 3：上传路径不改，只把限制写进文档

排查结论是官方 Python SDK 没有可用替代上传入口（1.0.4 与 1.0.9 的 `put_log_raw` 路径相同、protobuf 无 PkgId 字段）。因此本次不尝试改造上传，而是把"这份日志源无法做上下文查询"作为已知限制写进运行手册。

理由：在没有验证过可用路径的前提下改上传脚本，属于用猜测替代证据。

备选方案与取舍：

- **备选：改用控制台采集或新版接口。** 无法在仓库内验证，也不属于本项目可控范围；留给后续变更，前提是先有可复现的证据。

## Risks / Trade-offs

- **风险：把可修的情况误判为不可修。** 例如将来上游补上了定位字段，分类仍按"缺字段"处理。→ 缓解：检测依据仍是 `has_context_locator`，一旦字段出现即走正常路径；测试同时覆盖"有定位字段"分支。
- **风险：Replanner 拿到这条失败后仍然无法产出可信报告。** → 这是预期行为（证据不足就是不满足可信报告条件），不是回归。
- **权衡：不做重试会让"偶发缺字段"直接升级为换计划。** → 定位字段来自本轮已持久化的命中记录，不是外部偶发状态，重试无法改变结果。

## Migration Plan

无数据迁移：

1. 新增错误类型与分类映射。
2. `runtime` 的上下文分支改抛该错误。
3. 补测试与文档。
4. 真实 smoke：重跑一次需要上下文的诊断，确认只失败一次、原因可读、任务仍能以诚实报告收尾。

回滚：改动集中在分类映射与一处抛错点，可整块回退。

## Open Questions

（无）
