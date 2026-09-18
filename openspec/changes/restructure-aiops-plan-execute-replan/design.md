## Context

动机见 `proposal.md`。这里是决定实现方式的现状与约束。

**现状数据流**（`apps/backend/src/super_ai/aiops/`）：

```
planner 节点
  ├─ knowledge_retrieval 检索 SOP → 落证据
  ├─ tool_resolver.discover() → 20 个工具
  ├─ build_aiops_tool_registry() → 按 policy 过滤成 12 个
  └─ create_validated_plan(model, catalog, query_is_trusted) → PlanDraft（含参数）

executor 节点（纯代码）
  ├─ plan_step = current_plan[next_position]
  ├─ 三类工具各自的服务端半自动填参（注入 / 覆盖 / 从命中构建）
  ├─ validate_runtime_tool_input()（对 MCP 工具空转）
  └─ 调用 → normalize_tool_evidence() → 落证据

replanner 节点（调模型）
  └─ ReplanDraft{action, steps, reason} → continue / replan / report
```

**约束**：

- 工具必须真实、只读；不得引入写操作。
- 所有访问按 owner scope 过滤；凭据、Region、TopicId 不得进入模型上下文或日志。
- 诊断跑在 durable background job 内，节点完成即写 checkpoint，支持 lease 恢复。
- SSE 事件目录固定（`task.status`/`tool.call`/`reference.source`/`report`/`complete`/`error`），不得新增私有事件类型。
- 后端要求 Ruff + strict Pyright 通过；模块导入期不得建立外部连接。

**已核实的关键事实**（决定下面多数决策）：

| 事实 | 证据 |
|---|---|
| CLS MCP 20 个工具**没有一个**声明 `outputSchema` | 实测 `tools/list` |
| MCP adapter 为工具生成的输入模型只有一个 `root` 字段 | 实测 `DescribeTopicsInput.model_fields == ['root']` |
| 结果：`validate_runtime_tool_input` 对 MCP 工具**完全空转** | 实测垃圾键、空对象、缺必填三者全被放过 |
| 官方 `SearchLog` 参数说明要求先调 `ConvertTimestampToTimeString`，而它此前不在白名单里 | 读官方 schema 描述 + `git show HEAD:tool_policy.py` |
| 成功步骤的 `result_summary` 是写死的常量 `"真实工具调用成功"` | `runtime.py:460` + 数据库实测 |

## Goals / Non-Goals

**Goals:**

- 让"计划"与"取值"在时间上分离：计划时不猜值，执行时依据真实产出取值。
- 让工具集合由真实发现决定，而不是由"谁写过 adapter"决定。
- 让每一步的参数在调用前被真实 schema 校验，失败可分类、可追踪、可回看。
- 让 replanner 的判断建立在结构化的真实执行结果上，而不是模型自述。

**Non-Goals:**

- 不引入出参数值合理性校验（"类型合法但值是废话"本轮不解决）。
- 不做自适应重试预算。
- 不恢复 replanner 的换计划能力，也不删除其代码路径。
- 不改证据充分性判断规则、报告结构、SSE 契约与前端。

## Decisions

### D1 · planner 不再输出参数值

**选择**：计划只含工具名、用途、顺序；参数留空。

**备选：参数引用表达式**（计划里写占位符引用前面步骤的产出，例如引用第 2 步生成的查询，运行时再解析成真实值）。**否掉的理由**：实测 CLS MCP 的 20 个工具**没有一个声明 `outputSchema`**，模型写引用只能靠猜字段名——把"猜值"换成"猜字段名"，同一个坑换个地方。

**备选：保持现状 + 补说明书**。已由前置变更验证过：说明书补全后模型会先取时间、再生成查询，但到填 `SearchLog` 参数时仍然只能写"使用步骤3计算的起始时间戳"。说明书解决"不知道字段是什么"，解决不了"不知道字段的值"。

### D2 · executor 成为按步填参的模型节点

**选择**：每一步执行前调用模型，输入为该工具的完整参数说明 + 整份计划 + 前面步骤的真实产出 + 告警；输出为该步参数。

**备选：服务端按能力配对自动绑定**（现状：SearchLog 的 Query 自动取最近 query_artifact，DescribeLogContext 的定位字段自动取最近 log_hit）。**部分保留**——它能覆盖已知的几对，但覆盖不了"任意工具的任意跨步依赖"，而且模型填了又被覆盖会让填参失去意义。

**代价**：每步多一次模型调用。**净影响有限**——replanner 本轮不再调模型，省下与步骤数相同的调用次数，总量大致持平。

### D3 · 参数按敏感度划分归属

| 参数种类 | 归属 | 理由 |
|---|---|---|
| `Region` / `TopicId` | **服务端无条件注入**，且从模型可见说明中移除 | 它们是账号级权威配置，模型不该知道也不该覆盖 |
| 跨步参数（`Query`/`From`/`To`/`Time`/`PkgId`…） | **模型填写** | "从前面产出里取哪个值"正是它该判断的事 |

**硬规则**：交给模型填参用的前序产出必须是**完整值**，不得用摘要截断——被截一半的 Query 抄过去就是废的。

### D4 · 工具集合来自真实发现，policy 降级

policy 从"准入名单"降级为"语义登记表"：仍登记能力、只读属性、产物类型与哪些参数由服务端注入；**不再决定谁能进入模型视野**。

**备选：维持静态白名单。** 否掉——它已经挡住了官方工具说明自己推荐的工具，使模型"照说明书排计划"反而被拒。

### D5 · 通用入参校验按真实 schema 手写

**选择**：用既有的 `tool_schema_properties()` / `tool_schema_required()`（已兼容"标准 `properties` 包装"与"langchain-mcp-adapters 扁平映射"两种形态）做四件事：必填齐全、拒绝未声明键、类型匹配、范围/枚举合法。

**备选：继续用 `tool.get_input_schema().model_validate()`。** 否掉——实测该模型只有一个 `root` 字段，等于没校验。

### D6 · 未登记 adapter 的工具产物统一按中间产物落库

**选择**：真实发现但未登记 adapter 的工具可以执行，产物按中间产物持久化，不计入证据充分性判断。

**备选：不放开这些工具。** 否掉——正是这个选择造成了"白名单按谁写过 adapter 来定"的问题。

**代价**：这些工具查到的东西不算证据，报告可能标 `insufficient_evidence`。可接受：先让 planner 能选对工具，再逐个补 adapter 提升证据能力。

### D7 · 执行结果由代码组装

**选择**：代码依据 step 表、evidence 表与审计记录拼装结构化执行结果。

**备选：模型写执行总结。** 否掉——它的用途是给 replanner 判断，模型写的总结等于先替 replanner 判断过一遍；而且摘要必然压缩，判断"要不要换计划"恰恰需要细节。

**配套**：替换写死的 `result_summary="真实工具调用成功"`，改为记录真实产出的安全摘要。

### D8 · replanner 本轮降级为纯代码验证

**选择**：replanner 只依据代码规则（既有证据充分性判断 + 剩余步骤 + 预算）决定继续或出报告，不调用模型、不改计划。

**备选：保留模型 replan。** 本轮否掉——先让"执行—验证"这条链路稳定可测，换计划能力等验证稳定后再评估。代码路径（`ReplanDraft` / `replan()` / `MAX_REPLANS`）保留不删除，避免二次改动。

### D9 · 每步两次尝试 + 三类错误

**选择**：每个计划步骤最多两次 attempt；失败分"原样重试 / 修正后重试 / 不可重试"三类，分类结果写入执行结果。

**备选：按工具数量自适应的全局重试预算。** 否掉——重试次数与工具数量没有因果关系；更关键的是全局预算会被单个坏工具吃光，真实案例里 `DescribeTopics` 一个工具就耗尽全部尝试次数，导致后面三步一次都没跑，这与"避免网络抖动导致失败"的初衷相反。

**同时修正**：外部服务以执行错误形式返回的参数校验失败（`-32602` 一类）当前被归类为 `transport`（可重试），必须改判为入参错误。

### D10 · 取消 `query_is_trusted` 分支

**选择**：凡计划包含日志检索步骤，必须且只能有一个 query-builder 步骤在前。

**原因**：原设计的"服务端已有可信 Query"分支依赖 planner 在计划参数里写死一个 Query；而 D1 已取消计划参数，这条路会断。统一成一条路后，query-builder 的自然语言输入由 executor 依据告警填写。

### D11 · 两处既有脆弱点一并加固

1. **工具名匹配统一**：当前 `validate_plan` 精确匹配、policy `matches()` 宽松匹配（去分隔符 + 小写），两套标准。统一为宽松匹配，并在拒绝时给出近似候选。
2. **计划位置对齐**：`position` 字段与数组下标目前隐式一致（靠 `enumerate`），代码无断言。加断言或改为按 `position` 字段查找。

### D12 · 提示词四段式 + 字段描述

提示词统一为 **角色定义 / 任务 / 该做什么 / 输出结果** 四段，并在"输出结果"段写清每个字段的含义、合格样例与自查清单。

**同步补齐字段描述**：`PlanStepDraft.tool_name` / `purpose` 当前**没有任何 `description`**，模型只看到字段名。新增填参输出模型同样 MUST 带描述。提示词管全局规矩，字段描述管"这一格装什么"。

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| planner 不写参数后，计划校验失去"查询是否可信"的判断依据 | D10：强制 query-builder 步骤，校验改为检查步骤顺序而非参数内容 |
| executor 每步一次模型调用，时延与成本上升 | 计划步数上限 8；replanner 不再调模型，净调用数大致持平；提示词限制输入为"当前工具说明 + 计划 + 前序产出"而非全部工具 schema |
| 通用入参校验需兼容两种 schema 形态 | 复用既有 `tool_schema_properties()` / `tool_schema_required()`，不新造解析 |
| 放开工具后 planner 选择面变大，可能选与故障无关的工具 | 提示词约束"只按 SOP 与告警选工具"；报告门禁与证据充分性判断独立于工具数量 |
| **"类型合法但值是废话"仍拦不住**（如 `timeString` 填一句中文） | 本轮**明确不解决**，记入已知问题；后续变更引入出参数值合理性校验 |
| 执行结果含参数，可能泄露敏感值 | 复用既有脱敏：`redact_error` + 敏感参数键过滤；Region/TopicId 由服务端注入且不进入执行结果的参数回显 |
| `current_plan` JSON 形态变化影响进行中任务的恢复 | 保留 `PlanStep.arguments` 字段（计划阶段为空，执行阶段写真实值）；恢复时计划仍可解析，无需数据迁移 |
| 每步两次尝试可能在某些瞬时故障下不够 | 分类保证"原样重试"只在真正瞬时的错误上消耗预算；达到上限后如实记录，不再靠猜 |

## Migration Plan

1. **前置**：`expose-full-aiops-tool-schemas` 先通过全量门禁并归档，本变更在其成果之上实施，避免两个 diff 混合。
2. **无数据迁移**：不改表结构，不新增 Alembic revision。`PlanStep.arguments` 字段保留，计划阶段写空 dict。
3. **实施顺序**：先补测试（期望新行为失败）→ 改 `tool_policy` 去掉名单过滤 → 改 `planning` 提示词与计划结构 → 改 `tool_adapters` 通用校验 → 改 `tool_failures` 分类 → 重写 executor → 改 replanner 为纯代码 → 拼装执行结果。
4. **验证**：后端全量 pytest + Ruff + strict Pyright；`openspec validate --all`；`git diff --check`；真实 smoke 跑一次完整诊断，核对计划不含参数、参数来自前序产出、失败分类正确、执行结果完整。
5. **回滚**：本变更落在独立 commit，回滚即 revert；由于无迁移，回滚不需要数据修复。

## Open Questions

- 未登记输出 adapter 的工具，其产物在**下钻视图与报告引用**里是否应该展示？当前设计按中间产物落库、不进证据判断，展示层行为待实现时确认，不影响规格与任务拆分。
