# Design

## Context

见 `proposal.md - Why`。任务 `c27b1fa4` 的 `alerts=[]`，但 `search_log_window()` 在没有告警时直接抛错，导致 SearchLog 参数校验失败、任务重试。

需求见 `specs/schema-aware-aiops-tool-execution/spec.md`。

## Goals / Non-Goals

**Goals：**

- 纯 query 诊断仍能获得确定的服务端时间窗；
- 告警诊断的时间窗行为完全不变；
- 时间来源可注入、可测试。

**Non-Goals：**

- 不让模型重新生成 From/To；
- 不改窗口配置、模型或 UI；
- 不保证旧日志一定落在当前 15 分钟窗口内（那是数据时间对齐问题）。

## Decisions

### 1. 无告警时用服务端当前时间作锚点

`search_log_window(alerts, defaults, *, now)`：

- `alerts` 非空：沿用 `[min startsAt − before, max startsAt + after]`；
- `alerts` 为空：使用 `[now − before, now + after]`；
- `alerts` 非空但任一 `startsAt` 缺失/不可解析：继续明确失败。

### 2. `now` 由 runtime 的可注入时钟传入

`DiagnosticRuntime` 已有 `_now_ms`（测试可固定）。执行 SearchLog 时把它转换为 UTC `datetime` 传给 `search_log_window`，避免直接调用系统时钟导致测试不稳定。

备选：在函数内部调用 `datetime.now()`。不可测试，且同一任务不同步骤可能跨秒，不采用。

### 3. 失败语义保持不变

纯 query 诊断拿到窗口后，SearchLog 仍可能返回 0 条（例如日志早于 15 分钟）。这种情况下：

- 不再报"没有可用告警"；
- 按现有逻辑进入 empty_result / 报告流程；
- 报告诚实说明证据不足。

这是数据时间窗问题，不是本次输入兼容问题。

## Risks / Trade-offs

- **手动 query 的窗口可能覆盖不到旧日志** → 这是预期：窗口默认 `[now−15min, now]`；需要更早日志时应调大 `windowBeforeMinutes` 或重新上传/对齐日志。
- **now 与告警分支的规则不同** → 只在 `alerts` 为空时使用 now，有告警时严格按告警时间，避免回归。
- **测试确定性** → runtime 注入固定 `_now_ms`，单测直接传 `now`。

## Migration Plan

无数据库、配置或 API 迁移；回滚只需恢复函数与 runtime 调用。

## Open Questions

（无）
