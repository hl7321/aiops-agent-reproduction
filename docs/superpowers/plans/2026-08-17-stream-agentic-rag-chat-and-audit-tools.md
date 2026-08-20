# Agentic RAG 流式聊天与工具审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 使用 LangChain `create_agent` 建立由模型自主选择工具、按共享 SSE 合同输出、成功后持久化完整 assistant 消息并记录 owner-scoped 工具审计的聊天运行时。

**Architecture:** HTTP 层只负责 owner 校验、请求/响应合同和 SSE 生命周期；`AgentChatRunner` 负责历史裁剪与 `create_agent` 调用；`AgentEventMapper` 把真实模型/工具事件转换为共享 SSE；审计与聊天消息分别使用明确事务边界。知识检索工具在创建本轮 Agent 时绑定 `CurrentUser`，模型参数不能扩大 tenant scope。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、LangChain 1.x `create_agent`、LangGraph、Vue 3.5、Pinia 3、TypeScript 5.6、Vitest 2、pytest。

## 全局约束

- 先写验收/合同测试，再写实现；每个任务先看到预期失败，再最小修复。
- 禁止在 Agent 前无条件调用 `knowledge_retrieval`，禁止伪造 reasoning、引用、分数或失败兜底答案。
- user 消息在 Agent 开始前持久化；assistant 只在成功获得完整正文后一次持久化，失败不得留下半条 assistant 消息。
- 每轮使用新的 references/toolCallIds 容器；历史恢复仅读取对应 assistant message metadata。
- SSE `id` 使用 `<turnId>:<sequence>`，`sequence` 单调递增；最终正文按 Unicode 字符发 `content.delta`，`complete` 恰好一次。
- Repository、审计查询与知识工具全部显式 owner scoped；日志不记录 prompt、query、参数值、完整参数、工具输出、token 或 reasoning。
- 不覆盖或暂存当前工作树中与 P13 有关的未提交文件；每次 Git 操作只列出 P15 文件。

---

### Task 1：扩展共享 chat/SSE/OpenAPI 合同

**Files:**

- Modify: `packages/api-contracts/src/sse.ts`
- Modify: `packages/api-contracts/src/chat.ts`
- Modify: `packages/api-contracts/src/openapi.ts`
- Modify: `packages/api-contracts/src/index.ts`
- Modify: `packages/api-contracts/src/contract-manifest.ts`
- Modify: `packages/api-contracts/src/sse.test.ts`
- Modify: `packages/api-contracts/src/chat.test.ts`
- Modify: `packages/api-contracts/src/openapi.test.ts`
- Modify: `apps/backend/tests/contracts/test_chat_contracts.py`

**Steps:**

1. 先增加失败测试，约束公共 SSE 字段包含正整数 `sequence`，以及 stream 请求、工具审计 DTO/list response、stream/audit OpenAPI path。
2. 运行 `npm run contracts:test` 和 backend 对应合同测试，确认因类型/路径缺失而失败。
3. 定义 `ChatStreamMessageRequest`、`AgentToolCallAudit`、审计状态与分页外壳；SSE error 继续复用共享错误结构。
4. 在 OpenAPI 中加入 `POST /chat/sessions/{sessionId}/messages:stream` 和 `GET /chat/sessions/{sessionId}/tool-call-audits`，复用 bearer、401、403。
5. 运行 contracts typecheck/test 与 backend 合同测试，确认通过。

### Task 2：建立 agent tool call audit 迁移和 Repository 边界

**Files:**

- Create: `apps/backend/alembic/versions/20260817_0007_add_agent_tool_call_audits.py`
- Create: `apps/backend/src/super_ai/memory/sqlite/agent_audit_models.py`
- Create: `apps/backend/src/super_ai/memory/sqlite/agent_audit_repositories.py`
- Create: `apps/backend/src/super_ai/agent_audit/models.py`
- Create: `apps/backend/src/super_ai/agent_audit/repositories.py`
- Modify: `apps/backend/src/super_ai/memory/sqlite/models.py`
- Modify: `apps/backend/alembic/env.py`
- Create: `apps/backend/tests/memory/test_agent_audit_migration.py`
- Create: `apps/backend/tests/agent_audit/test_repository.py`

**Steps:**

1. 写 migration 测试，断言 `agent_tool_call_audits` 的 owner、父对象、状态、时间、duration、错误字段与索引存在，且无 `parentCallId`。
2. 写两个用户的 Repository 合同测试：create/start/complete/fail/list 全部以 `owner_user_id` 为首个业务参数，跨用户不可见。
3. 写 exactly-one-parent 测试：`chatSessionId` 与 `diagnosticTaskId` 必须二选一；chat parent 使用真实外键，diagnostic 暂保留受 CHECK 约束的标量。
4. 运行对应 pytest，确认迁移/实现缺失导致失败。
5. 实现不可变 audit records、Protocol 和 SQLite adapter；arguments 存 owner-scoped JSON，resultSummary/errorMessage 使用安全有界文本。
6. 运行 `uv run alembic upgrade head`、migration/repository 测试、Ruff、Pyright。

### Task 3：实现确定性的 SSE 事件映射与 Unicode 拆分

**Files:**

- Create: `apps/backend/src/super_ai/chat/agent_events.py`
- Create: `apps/backend/src/super_ai/chat/turn_context.py`
- Create: `apps/backend/tests/chat/test_agent_events.py`

**Steps:**

1. 测试 `TurnContext` 每轮生成独立 references/toolCallIds、稳定 turn id 和从 1 开始的 sequence。
2. 测试中文、emoji、组合字符按 Python Unicode code point 顺序产生单字符 `content.delta`，其他事件不拆分。
3. 测试 tool started/delta/completed/failed、reference、真实 reasoning、error、complete 的顺序和 `complete` 唯一性。
4. 运行测试看到缺失实现失败。
5. 实现纯内存 `AgentEventMapper`；只映射输入中确实存在的 reasoning，不推断或合成思考过程。
6. 运行单测、Ruff、Pyright。

### Task 4：实现 tenant-bound tools 和安全审计包装

**Files:**

- Create: `apps/backend/src/super_ai/chat/agent_tools.py`
- Create: `apps/backend/src/super_ai/agent_audit/service.py`
- Create: `apps/backend/tests/chat/test_agent_tools.py`
- Create: `apps/backend/tests/agent_audit/test_service.py`

**Steps:**

1. 测试 `get_current_time` 返回明确时区与 ISO 时间；通过注入 clock 保证确定性。
2. 测试 knowledge tool factory 接收当前用户并复用 P12 `create_knowledge_retrieval_tool`，模型传入的 filters 只能收窄权限。
3. 测试审计 wrapper 对 started/completed/failed 写完整生命周期与 duration，arguments 属于 owner-scoped 审计数据。
4. 用日志捕获测试证明只记录 argument key names，不记录 query、参数值、输出、prompt 或 token。
5. 运行测试确认失败，再实现工具工厂和审计 service。
6. 运行对应 pytest、Ruff、Pyright。

### Task 5：用 LangChain create_agent 实现可注入 Agent runner

**Files:**

- Create: `apps/backend/src/super_ai/chat/agent_runner.py`
- Create: `apps/backend/src/super_ai/chat/history.py`
- Create: `apps/backend/tests/chat/test_agent_runner.py`
- Create: `apps/backend/tests/chat/test_history.py`

**Steps:**

1. 测试历史按 session 序号恢复、按 P06 `contextWindowTokens` 从最旧消息裁剪，并始终保留当前 user 消息。
2. 测试 Agent factory 必须调用 LangChain 1.x `create_agent`，传入 chat model 和两个绑定工具；不得提前执行 knowledge tool。
3. 使用 fake agent event stream 覆盖模型不调用知识工具、自主调用知识工具、真实 reasoning、工具失败、provider 失败。
4. 测试 reference/toolCallId 只来源于当前轮工具结果，不继承上一轮。
5. 运行测试确认 runner 缺失失败。
6. 实现可注入 token counter、agent factory/model provider/tool factory；生产默认使用 `create_agent`，测试不联网。
7. 运行对应 pytest、Ruff、strict Pyright。

### Task 6：实现流式聊天事务编排和 SSE endpoint

**Files:**

- Modify: `apps/backend/src/super_ai/chat/service.py`
- Modify: `apps/backend/src/super_ai/chat/repositories.py`
- Modify: `apps/backend/src/super_ai/memory/sqlite/chat_repositories.py`
- Modify: `apps/backend/src/super_ai/chat/dependencies.py`
- Modify: `apps/backend/src/super_ai/chat/router.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Create: `apps/backend/tests/chat/test_stream_service.py`
- Create: `apps/backend/tests/chat/test_stream_api.py`

**Steps:**

1. 写 API 测试：owner 校验先于 user message 写入；跨用户返回 `AUTH_FORBIDDEN`；SSE content-type 与共享 envelope/error/request-id 规则一致。
2. 写 service 测试：user 先独立提交；成功后 assistant 一次性提交并保存本轮 references/toolCallIds；失败无 assistant 半消息。
3. 写两轮测试证明引用隔离，reload 从各自 assistant metadata 恢复。
4. 写断连测试：客户端消费中断不删除已完成 assistant；P15 不宣称 durable generation 或 Last-Event-ID。
5. 运行测试确认缺失 endpoint/编排失败。
6. 实现 `messages:stream`、runner dependency 和独立事务边界；assistant 持久化成功后再发逐字符正文与唯一 complete。
7. 将 tool/provider 失败映射成共享 SSE error，不生成替代答案。
8. 运行 chat 全部测试、Ruff、Pyright。

### Task 7：暴露 owner-scoped 工具审计查询 API

**Files:**

- Create: `apps/backend/src/super_ai/agent_audit/router.py`
- Create: `apps/backend/src/super_ai/agent_audit/dependencies.py`
- Modify: `apps/backend/src/super_ai/chat/router.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Create: `apps/backend/tests/agent_audit/test_api.py`

**Steps:**

1. 写 API 测试覆盖正常列表、稳定排序、统一 envelope、401、父 session 跨用户 403、audit 跨用户不可见。
2. 运行测试确认路由缺失失败。
3. 实现 `GET /chat/sessions/{id}/tool-call-audits`，先校验 owner-scoped session parent，再按 owner/session 查询。
4. 运行 agent audit 与 chat API 测试、Ruff、Pyright。

### Task 8：扩展前端 typed streaming transport 和 chat store

**Files:**

- Modify: `apps/frontend/src/chat/chatClient.ts`
- Modify: `apps/frontend/src/chat/chatClient.test.ts`
- Modify: `apps/frontend/src/stores/chat.ts`
- Modify: `apps/frontend/src/stores/chat.test.ts`
- Modify: `apps/frontend/src/transport/sseClient.ts`
- Modify: `apps/frontend/src/transport/sseClient.test.ts`

**Steps:**

1. 测试 stream client 注入 bearer/request-id、跨 chunk frame 解析、sequence/id 保留、共享 SSE union 类型收窄。
2. 测试 chat store 的当前轮正文、reasoning、tools、references、complete/error 状态；新一轮开始清空 live references。
3. 测试 401 清理受保护 store，领域数据不写 localStorage。
4. 运行 frontend test/typecheck，确认类型和行为缺失失败。
5. 实现 typed stream client 与 UI-ready store 状态，不提前实现完整 Chat 页面。
6. 运行 frontend typecheck/test/build。

### Task 9：端到端回归、OpenSpec 验证与归档

**Files:**

- Modify: `README.md`（只在需要补充验证方式时）
- Create: `docs/runbooks/agentic-rag-chat-smoke.md`
- Modify: `openspec/changes/stream-agentic-rag-chat-and-audit-tools/tasks.md`

**Steps:**

1. 使用 fake provider/tool 完成后端端到端测试：无工具、自主知识工具、time 工具、失败、两轮引用隔离、跨 owner。
2. 运行 migration：`cd apps/backend && uv run alembic upgrade head`。
3. 运行 backend 门禁：`uv run ruff check .`、`uv run pyright`、`uv run pytest`。
4. 运行 contracts：`npm run contracts:typecheck`、`npm run contracts:test`。
5. 运行 frontend：`npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build`。
6. 运行 `openspec validate --all` 与 `git diff --check`。
7. 若本机 ignored 配置和 Qwen/Milvus 服务可用，执行一次真实对话 smoke；否则在 runbook/验证报告中明确写“未执行”，不得声称通过。
8. 使用 `$openspec-verify-change` 检查 completeness/correctness/coherence，修复全部 CRITICAL 并处理 WARNING，重新跑受影响门禁。
9. 同步 delta specs 到主规格后使用 `$openspec-archive-change` 归档；确认 `openspec list --json` 无 active P15 change。
