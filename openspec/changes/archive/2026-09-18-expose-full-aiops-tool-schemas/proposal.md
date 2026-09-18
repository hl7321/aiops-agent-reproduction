# 把完整工具参数说明书交给模型并删除参数兜底

## Why

模型在排计划时填不对工具参数，根因不是模型能力不足，而是**它拿到的参数说明书被砍过**：`_safe_schema_summary` 把每个字段压缩成只剩 `type`，字段说明、取值范围、时间格式、默认值全部丢弃，稍复杂的字段类型还会写成 `unknown`。官方 MCP server 返回的完整 tool schema **本来就在手上**（`tool.args_schema`），是被我们自己裁掉的。

于是模型只能猜，而项目用一连串兜底去接住猜错：

| 模型实际填的 | 兜底替它做的 |
|---|---|
| `TopicId: "cart-service-log"`（编造） | 服务端强制覆盖 |
| `From: 1789646000`（秒级） | 检测到秒级自动乘 1000 |
| `Query` 填的是占位文本而不是真实查询 | 用 query artifact 覆盖 |
| 少填 `From`/`To` | 补最近 1 小时默认值 |
| 键名写成 `query`/`q` | 别名映射成 `Query` |

这些兜底掩盖了真实问题：**模型从一开始就没被告知该怎么填**。参数说明书补齐之后，兜底就从"必需"变成了"掩盖"。本次改动把两者一起处理：**说明书给全，兜底删掉**。

## What Changes

**一、把完整工具 schema 交给模型**

- 工具目录不再输出"只剩 type 的摘要"，改为输出官方 MCP server 返回的**完整 JSON Schema**：字段说明、类型、取值范围（enum）、格式、默认值、必填项一并保留。
- 唯一的裁剪规则是安全边界：**服务端权威字段（`Region`、`TopicId`）不进入给模型看的 schema，也不出现在必填列表里**。它们由服务端注入，模型既不需要知道、也不允许覆盖。
- Planner 与 Replanner 使用同一份完整目录。

**二、删除补偿性兜底**

删除以下"替模型猜错买单"的逻辑：

- 键名别名映射（`query`/`logQuery`/`q` → `Query`、`Text`/`Prompt`/`Question` → `Text`）
- 缺失时间范围的默认值填充
- 缺失查询的默认值填充
- 秒级时间戳自动换算为毫秒
- 非法时间窗口自动重置为最近 1 小时

**三、保留必要的边界**

- `Region`/`TopicId` 仍由服务端注入，模型与客户端都不得覆盖。
- `DescribeLogContext` 的 `Time`/`PkgId`/`PkgLogId` 仍来自本轮已验证命中。
- 工具输入校验、计划级策略校验、retry/replan/prermanent 路由与 attempt 上限不变。
- 参数填错的恢复路径改为：**校验失败 → 把错误和完整 schema 一起交回模型修正**（原有机制，不再靠静默兜底）。

**四、放行只读辅助工具**

当前 policy 把官方 server 的 20 个工具砍到 4 个。实测这 20 个**全部是只读查询类**（`Search*`/`Describe*`/`Get*`/`Query*`/`Convert*`），没有一个是写操作，因此"防止写副作用"在这台 server 上并没有挡掉任何东西；真正被挡掉的是官方**推荐配套使用**的工具。

最典型的是时间转换工具：官方 `SearchLog` 的 `From`/`To` 说明明确写着"应当先调用 `ConvertTimestampToTimeString` 获取当前时间，再调用 `ConvertTimeStringToTimestamp` 获取时间戳"。这两个工具不在 policy 里，模型根本调不到，只能自己硬猜时间戳——**这正是"默认最近 1 小时""秒级自动乘 1000"两条兜底存在的直接原因**。

因此 policy 改为登记两类工具：

- **证据型**：产出 `query_artifact`/`log_hit`/`log_context`/`metric` 等诊断证据（原行为不变）。
- **只读辅助型**：允许规划与调用，产出作为中间产物进入模型可见上下文，但不计入证据充分性判断。

具有外部写副作用的工具仍然 MUST NOT 进入计划。

**五、补齐业务校验**

删除五类静默补偿后，必须有显式拒绝顶上：时间窗口非法（`From >= To`、跨度过大、时间单位不符）不再被悄悄重置，而是直接以校验错误失败，并把完整参数说明与字段错误交回模型修正。

非目标：

- 不放宽任何安全边界，不把 Region/TopicId 的取值暴露给模型。
- 不修改工具发现、白名单与同名冲突策略。
- 不处理日志定位字段缺失（另立变更）。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: 工具目录必须提供完整参数 schema（仅隐藏服务端权威字段）；参数规范化不得再用静默兜底替代模型的输入。
- `schema-aware-aiops-tool-execution`: AIOps 工具 policy 必须放行官方只读辅助工具（如时间转换与索引查询），同时继续禁止写副作用工具进入计划。

## Impact

- 影响的模块：`apps/backend/src/super_ai/aiops`（`tool_policy` 的 schema 投影、`planning` 的参数规范化与提示词、`runtime` 的调用前准备）。
- 影响的接口：无 HTTP/SSE 形状变更；模型侧提示词内容变化，step 记录中的参数更接近模型原始输入。
- 依赖：无新增依赖。
- 风险：中。删除兜底后，模型填错会直接暴露为校验失败并触发修正重试；若模型持续填不对，需要的是一次真实评估而不是回退到静默兜底。
