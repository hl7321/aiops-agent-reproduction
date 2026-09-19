## Context

动机与证据见 `proposal.md`。这里记录实现现状与约束。

当前状态：

- `tool_policy._safe_schema_summary()` 遍历 `tool.args_schema` 的 properties，每个字段只保留 `{"type": ...}`，取不到类型就写 `"unknown"`；`required` 沿用官方列表。官方 schema **本来就在 `tool.args_schema` 里**，是这层函数把它裁掉的。
- `planning.normalize_search_log_arguments()` 在调用前做了六件"替模型兜底"的事：键名别名映射、缺省时间窗、缺省 Query、秒→毫秒换算、非法时间窗重置，以及 Region/TopicId 强制覆盖。
- `cls_tool_adapters.build_text_to_search_log_query_input()` 另有一组 `Text`/`Prompt`/`Question` 别名。
- `runtime.executor` 在空结果时会用告警里的 `incident_id` 等字段拼一条兜底查询（`_search_log_fallback_query`）覆盖模型给出的 Query，这是**重试策略**而非输入补偿。

约束（来自既有规格，本次不得放宽）：

- `clsLogUpload.region` 与 `clsLogUpload.topicId` 必须由服务端注入，**模型不得提供或覆盖**，其取值也不得进入模型可见内容、事件与审计。
- `DescribeLogContext` 的 `Time`/`PkgId`/`PkgLogId` 必须来自本轮已验证命中。
- attempt 上限、retry/replan/permanent 路由判定不变。

## Goals / Non-Goals

**Goals:**

- 让模型在排计划时看到与官方 MCP server 一致的完整参数说明，从而有能力把参数填对。
- 删除为"模型猜错"准备的静默补偿，让填错以校验错误的形式暴露并可被修正。

**Non-Goals:**

- 不放宽服务端权威字段的安全边界。
- 不改工具发现、白名单、同名冲突与审计策略。
- 不处理日志定位字段缺失（另立变更）。

## Decisions

### 决策 1：用"完整 schema 投影"替换"只剩类型的摘要"

新增一个投影函数：以官方 `args_schema` 为输入，输出**保留 description / type / enum / format / default / required** 的完整 JSON Schema，只额外做一件事——**移除服务端权威字段**（`Region`、`TopicId`）。

移除要同时作用于两处：从 `properties` 删掉、从 `required` 删掉。否则会出现"必填但看不见"的矛盾说明。

理由：模型要能填对，就必须看到字段用途与约束；而服务端权威字段既然不允许模型决定，就不该出现在它的说明书里。

备选方案与取舍：

- **备选：保留 Region/TopicId 但标注"由服务端填写"。** 模型可能仍会尝试填充，且"看得见却不许填"会制造困惑与无效 token。直接移除更干净。
- **备选：原样透传官方 schema（含 Region/TopicId）。** 违反"模型不得提供或覆盖这两个字段"的既有规格，不做。

### 决策 2：删除静默补偿，保留边界注入与校验

删除清单（`normalize_search_log_arguments` 与两个 adapter）：

1. 键名别名映射（`query`/`logQuery`/`q`、`Text`/`Prompt`/`Question`）
2. 缺失时间范围的默认值填充
3. 缺失查询的默认值填充
4. 秒级时间戳自动换算
5. 非法时间窗口自动重置

保留清单：

1. Region/TopicId 注入（安全边界）
2. 官方 schema 校验与必填检查（改为直接报错，不再先补默认值）

理由：这五条的共性是"模型没填对时替它填"，它们让参数错误失去反馈；有了完整说明书，正确的做法是让校验失败并把完整 schema + 字段错误交回模型修正。

### 决策 3：空结果后的告警关联查询**先保留**，并在提案中单列

`_search_log_fallback_query`（用告警里的 `incident_id`/`trace_id`/`alertname`/`service` 放宽一次查询）性质与上面五条不同：它不修改模型给的参数，而是在**真实结果为空**后，用**真实告警数据**再做一次有界尝试。

处理：本次**保留**，并在 design 与提案中显式列出，交由需求方决定是否在同一变更中删除。

备选方案与取舍：

- **备选：一并删除。** 会让"生成的查询过窄导致空结果"直接进入换计划，诊断成功率下降；但语义上更纯粹。
- **备选：保留但降级为可配置。** 引入新配置面，超出本次范围。

### 决策 4：只读辅助工具的登记与产物落库方式

policy 增加"证据型 / 只读辅助型"两类登记：

- 证据型：保持现有行为（`artifact_kind` 决定 evidence kind，参与证据充分性判断）。
- 只读辅助型：允许规划与调用，产物**以既有 `query_artifact` 类别落库**，从而进入 `_model_context` 的已持久化证据摘要，供后续步骤与 Replanner 读取；因为它不属于 `log_hit`/`log_context`/`metric`，自然不会计入 `evaluate_claim_evidence` 的支撑证据。

为什么复用 `query_artifact` 而不新增证据种类：新增种类要同时改共享契约（TypeScript 与 Python）、`diagnostic_evidence` 的 CHECK 约束，并补一条 Alembic 迁移；而 `query_artifact` 在契约里的定义就是"查询产物 / 中间产物"，语义吻合。新增种类留到辅助产物真的需要独立区分时再做。

**配套保护**：`_latest_query_artifact()` 目前只按 evidence kind 取最近一条带 `Query` 的产物。引入辅助工具后，必须额外约束"来源必须是 query-builder 工具"，否则某个辅助工具的产物若恰好含 `Query` 字段，会被误当成 SearchLog 的查询。

备选方案与取舍：

- **备选：新增 `tool_result` 证据种类。** 语义最清晰，但要动契约、约束与迁移，成本明显更高，且当前只有少量辅助工具。
- **备选：辅助产物不落库。** 会导致 Replanner 看不到转换结果，模型无法用上一步的产出构造下一步参数，等于白放开工具。

## Risks / Trade-offs

- **风险：删掉默认时间窗后，模型必须自己给出合法 From/To。** 若模型持续填不出，会表现为校验失败并消耗 attempt。→ 缓解：完整说明里已包含时间格式与用途说明；修正重试会把上一次的字段错误回传。若真实 smoke 显示模型仍不可靠，应据实记录并回退该条默认值，而不是重新引入全部兜底。
- **风险：提示词体积上升。** 官方 SearchLog schema 的字段说明较长（含使用指引）。→ 缓解：只暴露 policy 允许的工具（当前为 4 个），总体可控；必要时对单字段说明做长度上限，但不得丢弃字段用途与枚举。
- **风险：删除别名映射后，模型用 `query` 等小写键会直接失败。** → 这是预期：官方 schema 用 `Query`，说明书里写的就是 `Query`；修正重试会指出字段错误。
- **权衡：`_safe_schema_summary` 也曾作为"避免泄露内部字段"的手段。** → 本次以"移除服务端权威字段"这一条显式规则替代，语义更清楚，且仍满足安全约束。

## Migration Plan

无数据迁移：

1. 替换 schema 投影。
2. 删除五类补偿逻辑，保留边界注入。
3. 更新受影响测试（现有用例中有断言默认值与换算行为的，需要按新契约改写）。
4. 补测试：完整说明可见、权威字段不可见、参数不合规直接失败。
5. 真实 smoke：重跑诊断，确认模型能自行给出合法时间窗与查询，且不再依赖兜底。

回滚：schema 投影与补偿删除可分别回退。

## Open Questions

- `_search_log_fallback_query`（空结果后的告警关联放宽）是否也在本次删除，由需求方决定；本设计默认保留。
