# P17 会话记忆模式实施计划

> 执行时必须遵循 `openspec-apply-change`，按测试先行完成每个任务；完成实现后使用 `openspec-verify-change`，修复问题并重新跑完整门禁，最后同步规格与归档。

**目标：** 为每个 Chat session 增加可持久、owner-scoped 的三种记忆压缩模式，用摘要和未压缩消息组装模型上下文，并在候选 user 消息落盘前执行 95% 硬上限。

**架构：** `chat_sessions` 保存派生记忆状态；纯 token estimator 和 turn-boundary 函数负责可测试决策；memory coordinator 在一个 Prompt/Skill snapshot 上完成自动压缩、预算与 prepare；可注入 LLM summarizer 在事务外生成摘要，再用 owner + 预期高水位条件写回。完整 `chat_messages` 始终保留。

**技术栈：** Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2 async、aiosqlite、Alembic、LangChain `count_tokens_approximately`/chat model、pytest/pytest-asyncio/Ruff/Pyright；TypeScript 5.6 strict、Vue 3.5、Pinia 3、Vitest 2、共享 OpenAPI manifest。

---

## 任务 1：先固定共享合同

**文件：**

- 修改：`packages/api-contracts/contract-manifest.json`
- 修改：`packages/api-contracts/src/chat.ts`
- 修改：`packages/api-contracts/src/errors.ts`
- 修改：`packages/api-contracts/src/openapi.ts`
- 修改：`packages/api-contracts/src/chat.test.ts`
- 修改：`packages/api-contracts/src/index.ts`
- 修改：`apps/backend/src/super_ai/api_contracts.py`
- 修改：`apps/backend/tests/test_contract_manifest.py`

1. 写入 memory mode、session 字段、更新请求、两条 operation 与两个错误的预期测试，先运行 contracts/backend 定向测试确认失败。
2. 更新 manifest 和 TypeScript/Pydantic 定义，保持 camelCase 与 nullable 语义完全一致。
3. 定向运行 `npm run contracts:typecheck`、`npm run contracts:test` 与 backend contract tests。

## 任务 2：迁移与 owner-scoped Repository

**文件：**

- 新增：`apps/backend/migrations/versions/20260818_0009_add_chat_session_memory.py`
- 修改：`apps/backend/src/super_ai/memory/extended_sqlite/chat_models.py`
- 修改：`apps/backend/src/super_ai/chat/models.py`
- 修改：`apps/backend/src/super_ai/chat/repositories.py`
- 修改：`apps/backend/src/super_ai/memory/extended_sqlite/chat_repositories.py`
- 修改：`apps/backend/tests/chat/test_migration_and_repository.py`
- 修改：`apps/backend/tests/memory/test_migrations.py`

1. 先添加 fresh upgrade、默认值、check constraint、metadata 对账、owner scope、条件写回和 clear 重置测试。
2. 实现迁移与模型字段；确保 downgrade 只删 P17 列/约束。
3. 扩展不可变 records 和 Protocol，Repository 所有 memory 方法首参均为 owner。
4. 实现批量会话详情读取或等价无 N+1 路径、投影更新和 compare-and-set 摘要写回。
5. 运行 migration/repository 定向测试。

## 任务 3：实现纯预算与摘要边界

**文件：**

- 新增：`apps/backend/src/super_ai/chat/memory/__init__.py`
- 新增：`apps/backend/src/super_ai/chat/memory/tokens.py`
- 新增：`apps/backend/src/super_ai/chat/memory/turns.py`
- 新增：`apps/backend/src/super_ai/chat/memory/models.py`
- 新增：`apps/backend/src/super_ai/chat/memory/summarizer.py`
- 新增：`apps/backend/src/super_ai/chat/memory/service.py`
- 新增：`apps/backend/tests/chat/memory/test_tokens.py`
- 新增：`apps/backend/tests/chat/memory/test_turns.py`
- 新增：`apps/backend/tests/chat/memory/test_service.py`

1. 先用 monkeypatch/fake estimator 写 69/70/95 和负值失败测试。
2. 实现 `estimate_context_tokens`，生产只包装 LangChain 近似计数。
3. 写并实现完整 turn 边界、高水位、canCompact、摘要 + 未压缩上下文转换。
4. 用 fake chat model 写摘要增量、空结果、异常、日志不含正文和并发写回测试，再实现 summarizer/service。
5. 用显式 capability provider 覆盖缺失 profile，不读取 env、不在 import 时创建 client。

## 任务 4：重构 stream prepare 与 Agent 装配

**文件：**

- 修改：`apps/backend/src/super_ai/chat/stream_service.py`
- 修改：`apps/backend/src/super_ai/chat/history.py`
- 修改：`apps/backend/src/super_ai/chat/dependencies.py`
- 修改：`apps/backend/src/super_ai/chat_configuration/assembly.py`
- 修改：`apps/backend/src/super_ai/chat_configuration/agent.py`
- 修改：`apps/backend/tests/chat/test_stream_service.py`
- 修改：`apps/backend/tests/chat/test_history.py`
- 修改：`apps/backend/tests/chat_configuration/test_agent.py`

1. 先扩展 stream tests：owner 校验、三模式触发、候选拒绝不落盘、摘要后重算、配置 snapshot 一致。
2. 让 prepare 在 user insert 前调用 memory coordinator，并把固定 system prompt/model messages 放入 `PreparedAgentTurn`。
3. 让 runner 使用 prepare snapshot，移除生产路径对 `trim_chat_history` 的依赖；保留其测试或安全删除无调用旧函数。
4. 保持工具自主选择、真实 reasoning、引用隔离、assistant 成功后一次性保存和 audit 行为不变。
5. 增加共享 `AppError` 到 SSE error 映射，验证上下文错误与 provider 错误不泄露正文/凭据。

## 任务 5：API 与 DTO 投影

**文件：**

- 修改：`apps/backend/src/super_ai/chat/service.py`
- 修改：`apps/backend/src/super_ai/chat/router.py`
- 修改：`apps/backend/src/super_ai/chat/dependencies.py`
- 修改：`apps/backend/src/super_ai/api_responses.py`
- 新增/修改：`apps/backend/tests/chat/test_memory_api.py`
- 修改：`apps/backend/tests/chat/test_stream_api.py`

1. 先写更新模式、手动压缩、空边界、跨 owner、validation、capability 缺失和刷新 DTO 测试。
2. 实现 memory service dependency 与两条 endpoint。
3. 统一 session mapper，使 create/list/detail/append/clear/stream reload 返回同一记忆字段语义。
4. 确认 95% 在 StreamingResponse 创建前返回 409 failure envelope；流内 mapper 仍能发送同一 error model。

## 任务 6：前端 typed client/store

**文件：**

- 修改：`apps/frontend/src/chat/chatClient.ts`
- 修改：`apps/frontend/src/chat/chatClient.test.ts`
- 修改：`apps/frontend/src/stores/chat.ts`
- 修改：`apps/frontend/src/stores/chat.test.ts`

1. 先写 PUT/POST 请求、bearer/envelope、成功对账与 401 清理测试。
2. 实现 `updateMemoryMode`、`compactMemory` client/store actions。
3. 同时更新 session list 项和 selected detail，禁止 localStorage。
4. 确认没有 P19 composer UI 或移动专用交互。

## 任务 7：验证、修复、同步与归档

1. 从临时配置运行 `cd apps/backend && uv run alembic upgrade head`。
2. 运行 backend：`uv run ruff check .`、`uv run pyright`、`uv run pytest`。
3. 运行 contracts/frontend：`npm run contracts:typecheck`、`npm run contracts:test`、`npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build`、`npm run frontend:test:secret`。
4. 运行 `openspec validate --all`、`git diff --check`。
5. 使用 `$openspec-verify-change` 核对 artifacts 与实现；修复全部 CRITICAL、处理 WARNING，并重跑受影响门禁与最终完整门禁。
6. 同步 delta specs、归档 `add-session-memory-modes`，再次运行 `openspec validate --all` 与 `git diff --check`。
