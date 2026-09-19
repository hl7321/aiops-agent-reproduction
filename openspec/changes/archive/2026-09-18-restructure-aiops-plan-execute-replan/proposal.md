# 重构诊断三节点分工与工具参数归属

## Why

诊断计划的每一步都必须在 planner 的一次调用里写完全部内容，**包括工具参数**。但那一刻前面步骤的真实产出还不存在，模型只能填人话占位符。真实日志里出现过：

```json
{"From": "使用步骤3计算的起始时间戳", "To": "使用步骤3计算的结束时间戳"}
{": ": "order-service"}
```

第一条让 `SearchLog` 入参校验失败；第二条更隐蔽——工具照单全收，返回一个荒谬的时间戳 `-62135625943000`，系统还判它成功。**整条链路上没有任何一环能表达"这里其实没有信息"。**

同时还有两个既有缺陷被这次排查暴露：

1. **工具清单被一份手写白名单卡死。** MCP 真实发现 20 个只读工具，白名单只放行 12 个。连官方 `SearchLog` 参数说明里推荐的 `ConvertTimestampToTimeString` 都不在名单里——模型照着官方说明排计划反而被 `validate_plan` 拒绝。白名单的存在理由不是"这些工具危险"，而是"当时只给少数工具写过输入验证器与输出 adapter"，结果准入标准退化成了固定名单。
2. **executor 是纯代码节点，没有纠错能力。** 参数错了只在 `input_validation` 时调一次模型修参数，其余失败一律傻重试；`MCP error -32602: Input validation error` 甚至被归类成 `transport`（可重试），于是重试三次全打在同一个必填字段缺失上。

## What Changes

- **planner 不再输出工具参数。** 计划只描述"用哪些工具、按什么顺序、每步为了拿到什么"，明确不承担填值职责。
- **executor 变成模型节点。** 每一步执行前，依据该工具的完整参数说明、整份计划、前面步骤的真实产出和告警原文，为这一步生成参数；校验通过才调用。
- **工具清单不再按静态白名单过滤。** MCP 真实发现的只读工具全部提供给 planner；policy 从"准入名单"降级为"语义登记表"（登记产出标签与 adapter 归属）。
- **入参校验通用化。** 对所有工具按各自真实 schema 校验必填、未知键、类型与取值范围，修复当前对 MCP 工具**完全空转**的校验（实测垃圾键、空对象、缺必填三者全被放过）。
- **参数归属按敏感度切分。** `Region`/`TopicId` 继续由服务端注入且不出现在模型可见说明里；依赖前面步骤产出的字段（`Query`/`From`/`To`/`Time` 等）改由模型填。
- **重试策略改写。** 每个步骤最多 2 次尝试；错误分三类——"原样重试"（超时/限流/5xx/连接中断）、"修正后重试"（入参校验失败）、"不可重试"（配置、越权、schema 不兼容、输出无法翻译、权限）。不可重试错误 MUST 立即停止该步骤并把类型与原因写入执行结果，不得继续重试。同时修正 MCP `-32602` 被误分类为 `transport` 的问题。
- **executor 产出结构化「执行结果」。** 由代码拼装（不由模型撰写）：每一步的工具名、参数、尝试次数、每次失败的原因与是否可重试、成功时的真实产出、产出的证据及其标签。替换当前写死的 `result_summary="真实工具调用成功"`。
- **replanner 本轮降级为纯代码验证。** 用既有三层证据充分性判断决定"继续执行 / 出报告"，不再调用模型、不再改计划；`replan` 能力保留但本轮不触发。
- **两处既有脆弱点一并加固。** 工具名匹配统一为宽松匹配（当前 `validate_plan` 精确匹配、policy 宽松匹配，两套标准）；计划位置与数组下标的一致性加断言。
- **BREAKING**：`diagnostic_tasks.current_plan` 中每个步骤不再携带模型填写的参数。
- **BREAKING**：取消 `query_is_trusted` 分支——只要计划包含日志检索步骤，就必须先有一步生成查询。

非目标：

- 不改工具专属输出 adapter 的既有语义（`log_hit`/`log_context`/`metric`/`query_artifact` 的定义保持不变），未登记 adapter 的工具产出暂统一按中间产物落库。
- 不引入出参数值合理性校验（`-62135625943000` 这类"类型合法但值是废话"的问题本轮不解决，留待后续变更）。
- 不改 SSE 事件目录、前端、报告结构与证据充分性判断的既有规则。
- 不恢复 replanner 的换计划能力，也不删除其相关代码路径。

## Capabilities

### New Capabilities

（无新增能力，本次改动全部落在既有能力的需求变更上。）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: 工具集合不再使用静态白名单过滤；入参校验改为按真实 schema 通用校验；参数归属、重试策略与执行结果形态改写。
- `aiops-diagnosis-and-evidence`: planner 只输出步骤、工具名与顺序；executor 变为按步填参的模型节点并产出结构化执行结果；replanner 只做代码级证据验证。

## Impact

**后端代码**

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/planning.py` | planner / executor 提示词重写；`PlanStepDraft` 去参数并补字段描述；新增填参方法；`validate_plan` 去 `query_is_trusted` 分支、匹配放宽 |
| `apps/backend/src/super_ai/aiops/runtime.py` | executor 节点重写；replanner 改纯代码验证；拼装执行结果；重试上限与分类分流 |
| `apps/backend/src/super_ai/aiops/tool_policy.py` | 去掉名单过滤，保留语义登记与模型可见 schema 投影 |
| `apps/backend/src/super_ai/aiops/tool_adapters.py` | 通用入参校验；未登记工具的统一中间产物兜底 |
| `apps/backend/src/super_ai/aiops/tool_failures.py` | 拆分"原样重试/修正后重试"；修 MCP `-32602` 分类 |
| `apps/backend/src/super_ai/aiops/evidence_policy.py` | 预期不变（三层判断保留）；仅在编译或引用受阻时最小调整 |
| `apps/backend/src/super_ai/aiops/models.py` | 视实现决定 `PlanStep.arguments` 的去留与执行结果领域模型 |

**数据与迁移**：不改表结构，无 Alembic 迁移；`current_plan` 的 JSON 形态变化只影响进行中的任务。

**契约与前端**：无新增或修改 HTTP/SSE 契约，无前端改动。计划进度继续复用 `task.status.data.message/progress`。

**测试**：`test_contracts_and_planning.py`、`test_runtime.py`、`test_tool_policy.py`、`test_tool_recovery.py`、`test_evidence_policy.py` 需同步更新；新增填参、重试分流、执行结果、通用入参校验的用例。

**前置依赖**：`expose-full-aiops-tool-schemas` 已实现但未归档，本变更建立在其成果之上（完整 schema 投影、辅助工具放行、五条参数兜底已删除）。实施前该变更须先通过门禁并归档，避免两个变更的 diff 混在一起。
