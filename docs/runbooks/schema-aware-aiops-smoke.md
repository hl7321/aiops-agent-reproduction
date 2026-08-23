# Schema-aware AIOps 真实联调记录

P28 的自动化验证使用受控 provider/MCP 边界，证明 Schema 校验、重试、证据门禁和知识提升逻辑；它不能替代真实腾讯 CLS、Qwen、Milvus 与官方 CLS MCP 的联合验收。

## 本次状态

- 自动化工程门禁：按 P28 tasks 记录执行。
- 真实外部 smoke：**未执行**。
- 原因：本轮没有重新获得针对 P28 外部调用的明确授权。日志上传、远端查询和模型调用可能产生费用或外部状态，因此不复用此前演示授权，也不把 fake 测试描述为真实联调。

## 获得明确授权后的验收顺序

1. 启动本地五服务、后端、前端和官方 CLS MCP Server，确认 `/ready` 中 SQLite、Milvus、Qwen、MCP 均可用。
2. 使用可信 CQL 调用 SearchLog，确认返回非空 `Time`、`PkgId`、`PkgLogId`，且权威 `Region`、`TopicId` 来自 ignored 本机 JSON。
3. 使用自然语言条件，经 TextToSearchLogQuery 生成查询后调用 SearchLog，确认 query artifact 与 log hit 均被持久化。
4. 对需要调用顺序、重试或恢复时序的结论，使用 SearchLog 命中定位字段调用 DescribeLogContext，确认产生 `log_context` evidence；缺少必要上下文时不得生成可信报告。
5. 完成 `verified_evidence`、`uncertainty=false` 的报告，提交当前 owner 的 positive report feedback，再显式提升为 case。
6. 等待 durable indexing 成功，并用下一轮 owner-scoped knowledge retrieval 命中新 case；检查重复提升只追加 provenance，不产生第二份向量内容。

每一步均须保存脱敏 request ID、任务 ID、步骤 attempt、evidence ID 与 case/index task ID；不得记录凭据、完整查询参数、原始日志正文或模型正文。
