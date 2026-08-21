## Why

P20 已提供真实活跃告警和显式 CLS 日志输入，但系统还不能在客户端断开或进程重启后持续执行可追溯诊断。P21 需要把 SOP、真实 MCP 工具结果、计划、证据、checkpoint 和报告纳入同一套 owner-scoped durable workflow，确保任何产品结论都能回到真实证据。

## What Changes

- 增加 LangGraph Planner → Executor → Replanner → Report 状态图，设置明确的计划步数和重规划上限，并由 P09 durable job 执行。
- Planner 先使用当前 owner 的 `knowledge_retrieval` 获取 SOP，再发现当前 owner enabled MCP tools；最终计划只允许一个真实 SearchLog 类步骤，缺少该工具时明确失败。
- Executor 只调用已注册的知识或 MCP 工具，Replanner 只根据已有证据继续、调整或进入报告，禁止补造成功、日志或证据。
- 增加 owner-scoped 诊断任务、步骤、规范化证据、报告、报告证据关联和图 checkpoint 持久化；复用通用 tool call audit 和 background job/event。
- 增加诊断创建、列表、详情、证据链和持久事件流 API；取消与重试继续复用 background-job API，不增加诊断专用路由。
- 扩展共享 contracts、Pydantic 和机器可读 OpenAPI，定义诊断 DTO、状态映射、证据、报告 provenance 和五个认证 path；流只复用现有 SSE union。
- 报告只根据告警、SOP、计划和真实证据生成固定中文 Markdown；模型失败时使用诚实的结构化 fallback，并明确证据不足和不确定性。
- 本 change 不实现 AIOps 前端最终工作区、不上传模拟日志、不自动执行处置，也不把 fake provider 输出作为产品证据。

## Capabilities

### New Capabilities

- `aiops-diagnosis-and-evidence`: 定义可恢复诊断图、durable job 生命周期、owner-scoped 规范化证据、checkpoint、报告 provenance、持久 SSE 回放和诚实 fallback。

### Modified Capabilities

- `api-and-sse-contracts`: 增加诊断任务/步骤/证据/报告 DTO、状态映射和五个 bearer-protected AIOps path，并约束只使用既有 SSE event union。

## Impact

- 后端新增 `super_ai.aiops` 图、服务、handler、Repository Protocol、SQLite adapter、依赖和路由模块，并把 handler 注册到配置化 FastAPI lifespan。
- Alembic 新增六张规范化表，并为 owner、task、step、evidence 和 report 关联建立索引/外键；现有 background jobs 与 agent tool audits 继续作为通用运行时边界。
- `packages/api-contracts`、Pydantic 合同和 manifest 增加诊断类型与 OpenAPI operations；不增加 plan/step/replan SSE type。
- 测试只在 provider/MCP 边界使用可控 fake，断言产物不会冒充真实产品结论；真实 CLS MCP + Qwen smoke 仅在用户环境具备且目标明确时执行并如实记录。
