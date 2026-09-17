## Context

动机见 `proposal.md`。这里只记录现状与约束。

当前状态（均已实测）：

- `cls_tool_adapters._extract_generated_query()` 从返回文本里用正则取出 `sql` 围栏代码块，然后只做"截断 `| SELECT` 之后的解释文字"与去空白，**不做反转义**。
- `unwrap_mcp_payload()` 拿到的是一段**嵌在 JSON 里的转义文本**（`Content: {"Choices":[{"Message":{"Content":"...```sql\nservice:\"...\"\n```..."}}]}`），因此正则抠出的代码块带着 `\n`、`\"` 这类字面量转义。
- 实测：把真实 MCP 返回喂给 `parse_text_to_search_log_query_result()`，产出的 Query 是 `'\nservice:\"auth-service\" AND level:\"ERROR\"\n'`；而 CLS 对它的回答是 `SyntaxError [field: nservice, can not search on this field]`。
- `tool_failures._failure()` 目前把 `safe_detail` 设为 `type(error).__name__`，服务端原话被丢弃，因此诊断只显示 `transport: _MCPToolExecutionError`。
- 仓库已有 `background_jobs.security.redact_error(message, serialized_payload)`：按**键名标记**（password/secret/token/apikey/authorization）替换值，并处理 `Bearer xxx` 与 `key: value` 形式。它**不会**抹掉 Region/TopicId 这类非密钥但同样不该外露的值。

约束：

- 不得改变 attempt 上限、退避策略与 retry/replan/permanent 的路由判定。
- 错误消息会进入 step、tool audit 与持久事件，必须脱敏且有界。
- Region/TopicId 属于服务端权威参数，既不得由模型修改，也不得出现在失败摘要里。
- Python 3.10+，strict Pyright，Ruff。

## Goals / Non-Goals

**Goals:**

- 让 query-builder 的产物成为**可直接执行**的查询文本。
- 让工具失败的**可读原因**在系统内可见，同时不泄露敏感值。

**Non-Goals:**

- 不改外部服务的返回格式，也不试图让模型换一种输出方式。
- 不引入新的证据种类、事件类型或 HTTP 形状。
- 不改 `PkgId`/`PkgLogId` 相关的上下文能力。

## Decisions

### 决策 1：反转义放在中间产物 adapter 层

在 `_extract_generated_query()` 返回前做一次反转义，而不是在 `runtime` 取用时或调用工具前补。

理由：adapter 的职责就是"把外部返回翻译成本地可用产物"；把它放在这里，产物一旦落库即为可执行文本，后续路径（含纠错模型、事件回放）看到的都是干净查询。

备选方案与取舍：

- **备选 A：在调用 SearchLog 前临时反转义。** 只修一处调用点，但落库的 `query_artifact` 仍是脏的，纠错模型与人工排查都会被误导。
- **备选 B：让模型不要用代码块。** 依赖模型行为，不稳定，且外部工具格式不受我们控制。

### 决策 2：反转义采用"先严格解码、失败再按已知序列替换"

实现策略：

1. 若文本包含转义序列，先尝试按 JSON 字符串解码（把文本包成 `"..."` 再解析）。
2. 解码失败时，退化为只替换已知安全序列（`\n`、`\r`、`\t`、`\"`、`\\`）。
3. 文本本来就没有转义时，保持原样，不做任何改动。

理由：来源确实是 JSON 转义文本，严格解码最准确；但查询里可能出现 CLS 自己的反斜杠（例如正则片段 `\d`），严格解码会失败，此时**绝不能抛错把诊断打挂**，退化为定向替换更稳。

备选方案与取舍：

- **备选：只做定向替换，不做严格解码。** 简单，但遇到 `\uXXXX` 之类的转义就还原不完整。
- **备选：无条件 `json.loads`。** 遇到非转义文本会直接抛错，风险最高。

### 决策 3：失败摘要按"密钥标记 + 敏感参数键"双重脱敏

保留服务端消息片段，但先过两道脱敏：

1. 复用现有 `redact_error()`，处理凭据类值。
2. 追加按**参数键名**的脱敏：把 `Region`、`TopicId`（以及同类服务端权威字段）在参数里的**值**从消息中抹掉。

为此，`classify_tool_failure()` 需要接收调用参数（或预先算好的敏感值列表），而不是只接收异常与阶段。

理由：`redact_error` 只认识密钥类键名，Region/TopicId 的值会原样留着——而这两个值恰恰是"不该进日志与事件"的敏感上下文。

备选方案与取舍：

- **备选：按正则猜 UUID / `ap-` 前缀。** 能覆盖 TopicId 与 Region 的常见形状，但属于猜，容易漏也容易误伤。
- **备选：完全不记录消息。** 就是现状，正是本次要修的问题。

### 决策 4：只改"说了什么"，不改"怎么处理"

失败摘要变详细，但 `category`、`route`、`retryable`、`delay` 的判定逻辑完全不动。

理由：本次的目标是可观测性，不是行为变更；把两者混在一起会让回归风险与验收边界都变模糊。

## Risks / Trade-offs

- **风险：服务端消息携带敏感值。** → 双重脱敏 + 有界长度（摘要截断，`safe_message` 保持既有上限）；并补一条测试专门断言 Region/TopicId 不出现在结果里。
- **风险：反转义误伤合法反斜杠。** → 采用"严格解码失败即退化"的策略，并在测试中覆盖含 `\d` 这类片段的查询。
- **风险：错误摘要进入持久事件后体积膨胀。** → 摘要长度设上限，且只在失败路径写入。
- **权衡：`classify_tool_failure` 的签名变化会影响调用点。** → 目前只有 `runtime.executor` 一处调用，改动面可控；同步更新既有测试。

## Migration Plan

无数据迁移：

1. adapter 反转义。
2. 失败分类接收参数并双重脱敏。
3. 补测试，跑门禁。
4. 真实 smoke：重跑诊断，确认 SearchLog 用生成查询直接命中，且失败摘要可读。

回滚：两处改动互相独立，可分别回滚。

## Open Questions

（无）
