## 1. 共享合同与迁移边界

- [x] 1.1 先增加 contracts 失败测试，覆盖诊断 DTO、五个受保护 path、状态映射、`SYSTEM_AIOPS_SEARCH_LOG_UNAVAILABLE`、task progress 和禁止诊断专用 cancel/retry/private SSE type，再同步 TypeScript、manifest 与 Pydantic。
- [x] 1.2 先增加 fresh upgrade/metadata 失败测试，再建立 `diagnostic_tasks`、`diagnostic_steps`、`diagnostic_evidence`、`diagnostic_reports`、`report_evidence_links`、`graph_checkpoints` Alembic 迁移及 SQLAlchemy models。
- [x] 1.3 定义不可变 diagnosis records 与 owner-first Repository Protocol；先用两个 user 写跨租户、计划版本、步骤排序、证据查询、checkpoint 单调和 report link 同 owner/task 失败测试，再实现 SQLite adapters。

## 2. Durable runtime 与持久事件

- [x] 2.1 先增加 background job termination reason 与 owner-scoped semantic progress event 失败测试，再最小扩展 P09 context/worker/store，保持现有 lease、heartbeat、retry 和 lifecycle 行为。
- [x] 2.2 先增加创建事务和状态映射失败测试，再实现 diagnostic task + alert evidence + `aiops_diagnosis` job 的原子创建、最新 resource job 对账及 accepted/running/succeeded/failed/cancelled 更新。
- [x] 2.3 先增加 restart/cancel/retry/timeout 测试，证明 handler interruption 只在真实取消/timeout 写终态、shutdown 保留可恢复 running，retry 复用同一 task/checkpoint 且不丢失 evidence。

## 3. Planner 与工具权限

- [x] 3.1 先增加 SOP/no-SOP/检索失败和调用顺序测试，再实现 planner 在 MCP discovery 前调用 owner-scoped knowledge retrieval，并把真实引用保存为 knowledge evidence/audit。
- [x] 3.2 先增加 enabled/disabled/cross-owner MCP discovery、SearchLog 名称规范化和同名冲突测试，再实现 request/job-scoped 真实工具注册表；无 SearchLog 时用稳定 503 错误失败且不调用 planner model。
- [x] 3.3 先增加 1..8 步、恰好一个 SearchLog、未注册工具、重复 SearchLog 和模型修正上限测试，再实现 structured PlanDraft、服务端二次校验和 plan version 持久化。

## 4. Executor、Replanner 与证据

- [x] 4.1 先增加逐步执行、started/completed/failed audit、参数键日志和取消检查测试，再实现一次只执行一个持久 step 的 Executor。
- [x] 4.2 先增加 knowledge/log/metric/alert normalizer 的有界内容、脱敏、未知 payload 拒绝和无 fake 证据测试，再实现规范化 evidence 写入及 reference/tool semantic events。
- [x] 4.3 先增加 continue/replan/report、工具失败、未注册重规划、计划版本和最大三次重规划测试，再实现只消费已有 step/evidence 摘要的 structured Replanner。

## 5. LangGraph 与 checkpoint 恢复

- [x] 5.1 先增加图拓扑失败测试，再实现 `START→planner→executor→replanner→(executor|report)→END` StateGraph 和有界条件边，禁止独立循环或进程内临时任务。
- [x] 5.2 先增加每节点事务、最后完整节点恢复、未提交节点重做和 evidence id rehydrate 测试，再实现 owner-scoped checkpoint save/load 与 graph resume。
- [x] 5.3 将 graph runner 包装为惰性 `aiops_diagnosis` background handler，在显式任务运行期注入 Qwen、retrieval、MCP、audit 和 repositories；增加 import/app-start 无联网测试并注册到 lifespan registry。

## 6. 报告与 provenance

- [x] 6.1 先增加固定中文标题、多告警编号、只使用真实输入和 claim evidenceIds 校验测试，再实现 structured report draft、Markdown 结构校验和同 owner/task report links。
- [x] 6.2 先增加模型异常、非法标题、跨任务 evidence、证据不足和零工具结果测试，再实现纯函数 fallback；只摘录已有 evidence，固定标注不确定性且不生成根因/日志/指标。
- [x] 6.3 先增加 report/reference/task progress 持久 event 测试，证明关键结论 links 可从 evidence-chain 追溯，建议不被写成已执行事实。

## 7. API 与 SSE 恢复

- [x] 7.1 先增加创建、列表排序、详情、证据链、认证、跨租户和统一 envelope 测试，再实现四类 JSON API 与 owner-scoped dependencies/router。
- [x] 7.2 先增加 afterSequence=0/中途恢复、轮询、断连不取消、terminal complete 恰好一次和错误复用测试，再实现 `POST /aiops/diagnostics/{id}:stream` 的持久 job event→共享 SSE 映射。
- [x] 7.3 增加仓库治理测试，禁止 plan/step/replan 新事件、诊断专用 cancel/retry、生产 fake evidence/provider、敏感 query/args/tool output 日志和 import-time 外部 client。

## 8. 验证与归档准备

- [x] 8.1 执行 `uv run alembic upgrade head`、backend `uv run ruff check .`、`uv run pyright`、`uv run pytest` 及 contracts typecheck/test，修复全部问题。
- [x] 8.2 执行 `openspec validate --all` 与 `git diff --check`；本机 Compose 服务当前未运行，无法同时满足真实 Qwen、Milvus、已索引 SOP 和 owner enabled 官方 CLS MCP SearchLog，故未执行真实 smoke，且不以 fake 单测冒充。
- [x] 8.3 使用 `$openspec-verify-change` 逐项核对 tasks、requirements、scenarios 和 design，修复所有 CRITICAL/WARNING 后重新运行受影响门禁。

归档动作：验证通过后同步全部 delta specs，使用 `$openspec-archive-change` 归档，并按用户约定执行 Conventional Commit 保存 P21；归档和 Git commit 不作为归档前 checkbox。
