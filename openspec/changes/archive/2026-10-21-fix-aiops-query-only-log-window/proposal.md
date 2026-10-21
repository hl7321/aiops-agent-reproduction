# 修复仅 query 诊断的日志时间窗

## Why

任务 `c27b1fa4` 是一次**只输入 query、没有选择告警**的诊断：

- query：`order-service 的 OrderDatabasePoolExhausted`
- alerts：`[]`

模型本身正常：`TextToSearchLogQuery` 成功生成了查询。但 `SearchLog` 连续两次失败：

```
input_validation: ValueError: 没有可用告警，无法计算日志时间窗
```

报告因此进入 `execution_failed`，后台任务按 durable runtime 重试了 3 次。

根因是上一次"时间窗服务端注入"只处理了**有告警**的情况，默认必须有 `startsAt`；而项目本身支持手动 query 诊断。这是新逻辑对既有能力的回归，不是模型报错。

## What Changes

**1. 无告警时使用服务端当前时间作为锚点。**

- 本轮有告警：保持现有规则 `[最早 startsAt − before, 最晚 startsAt + after]`；
- 本轮没有告警（纯 query 诊断）：使用服务端当前时间 `now`，窗口为 `[now − before, now + after]`；
- 有告警但 `startsAt` 缺失或不可解析：仍然明确失败，不静默猜测。

**2. 时间来源可测试、可注入。**

- `search_log_window()` 增加 `now` 参数；
- runtime 使用已有的可注入时钟（`_now_ms`）生成 UTC 时间，测试可固定时间。

**3. 补回归测试与真实 smoke。**

- 单测覆盖 `alerts=[]` 的时间窗；
- runtime 测试覆盖纯 query 诊断仍能进入 SearchLog，并且参数带 From/To；
- 现有告警窗口测试保持不变；
- 真实 smoke 提交一次纯 query 诊断，确认不再出现"没有可用告警"的输入校验错误。

非目标：

- 不改告警窗口规则、窗口配置或模型选择；
- 不让模型重新生成 From/To；
- 不改 API、DTO、数据库或前端。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: 仅 query 诊断使用服务端当前时间作为日志窗口锚点。

## Impact

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/planning.py` | `search_log_window` 增加 `now` 参数与无告警分支 |
| `apps/backend/src/super_ai/aiops/runtime.py` | 用 runtime 时钟传入 `now` |
| `apps/backend/tests/aiops/` | 单测 + runtime 回归 |

**契约/数据**：无改动。
