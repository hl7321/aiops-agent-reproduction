# Schema-aware AIOps 真实联调记录

P28 的自动化验证使用受控 provider/MCP 边界，证明 Schema 校验、重试、证据门禁和知识提升逻辑；它不能替代真实腾讯 CLS、Qwen、Milvus 与官方 CLS MCP 的联合验收。

## 本次状态

- 自动化工程门禁：按 P28 tasks 记录执行。
- 真实外部 smoke：**未执行**。
- 原因：本轮没有重新获得针对 P28 外部调用的明确授权。日志上传、远端查询和模型调用可能产生费用或外部状态，因此不复用此前演示授权，也不把 fake 测试描述为真实联调。

## 获得明确授权后的验收顺序

1. 启动本地五服务、后端、前端和官方 CLS MCP Server，确认 `/ready` 中 SQLite、Milvus、Qwen、MCP 均可用。
2. 使用可信 CQL 调用 SearchLog，确认返回非空 `Time` 与日志内容，且权威 `Region`、`TopicId` 来自 ignored 本机 JSON。**注意**：当前日志上传链路产不出上报包 ID，`PkgId`/`PkgLogId` 恒为空字符串，这不属于失败。
3. 使用自然语言条件，经 TextToSearchLogQuery 生成查询后调用 SearchLog，确认 query artifact 与 log hit 均被持久化。
4. 验证结论依赖的"前后过程"由**日志检索结果自身**提供：同一条故障链路的日志按发生顺序一起返回，因此一次 SearchLog 即足以支撑时序结论，不需要调用日志上下文工具。
5. 完成 `verified_evidence`、`uncertainty=false` 的报告，提交当前 owner 的 positive report feedback，再显式提升为 case。
6. 等待 durable indexing 成功，并用下一轮 owner-scoped knowledge retrieval 命中新 case；检查重复提升只追加 provenance，不产生第二份向量内容。

每一步均须保存脱敏 request ID、任务 ID、步骤 attempt、evidence ID 与 case/index task ID；不得记录凭据、完整查询参数、原始日志正文或模型正文。

## 当前数据源的证据能力边界（2026-09-19 实测）

| 能力 | 状态 | 判定依据 |
|---|---|---|
| 日志检索（SearchLog + TextToSearchLogQuery） | ✅ 可用 | 真实命中并落库 `log_hit` |
| 日志自带链路顺序 | ✅ 可用 | 一次按 `incident_id` 检索返回同一链路连续多行 |
| 单条日志前后文（DescribeLogContext） | ❌ **已退役** | 必填的 `PkgId`/`PkgLogId` 只能来自 SearchLog 命中，而本上传链路恒返回空串 |
| 指标查询（QueryMetric / QueryRangeMetric） | ❌ **已退役** | 需要指标主题（BizType=1），当前账号只有日志主题 |
| CLS 告警查询与告警配置查询 | ⚠️ 静默为空 | 本项目告警来自 Alertmanager，CLS 侧没有对应数据 |

### 退役判定依据（可复现）

1. 直接读取 SearchLog 原始返回（绕开本地解析层）：`PkgId` 与 `PkgLogId` 是 CLS 返回的空串。
2. `tencentcloud-cls-sdk-python` 全量搜索 "pkg"：零匹配——请求类、响应类与 protobuf 都没有这个概念，因此**换任何日志内容都无法产出包 ID**。
3. 上传时在内容里显式写 `PkgId` 后再调用上下文工具：服务端不报错，但返回 `LogContextInfos: []`——伪造的包 ID 找不到包。
4. `DescribeTopics` 指定 `BizType=1` 查询：指标主题 0 个。

### 备选方案（当前不启用）

如果将来换成能产出定位字段的日志来源，或首次检索过窄需要二次扩宽，可以用**第二次日志检索**按同一链路标识（例如 `context_flow_id` / `trace_id`）加时间窗取上下文。

启用条件：数据源真实支持，且第一次检索无法覆盖链路上下游。当前数据源上这一步是多余的——实测按链路标识再查一次返回的是完全相同的行。
