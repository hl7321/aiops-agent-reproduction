# Chat Session Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立完全由服务端 SQLite 管理、owner-scoped、可供后续流式 Agent 复用的聊天会话与消息生命周期。

**Architecture:** 使用独立 Chat 领域层组织不可变 record、Repository Protocol、ChatService 与 FastAPI router，SQLite adapter 位于 `super_ai.memory.extended_sqlite`，Alembic 是 schema 唯一权威。TypeScript contracts 与机器可读 OpenAPI 先定义形状，Python Pydantic 镜像和前端 typed client/store 通过合同测试保持一致。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy 2 async、aiosqlite、Alembic、pytest、TypeScript 5.6 strict、Pinia 3、Vitest 2、OpenSpec。

## Global Constraints

- 所有受保护 Repository 方法首个业务参数必须是 `owner_user_id`，SQL 必须在同一语句中包含 owner scope。
- 后端只允许 `from super_ai...`，模块 import 期间不得连接 SQLite、Milvus、LLM 或 MCP。
- ChatService 只依赖 Repository Protocol 与不可变 record，不接收 ORM model 或 `AsyncSession`。
- 会话与消息只保存在服务端 SQLite；前端 localStorage 仍只允许认证 token。
- 本阶段不调用模型、不实现 SSE、不修改 Chat 产品页面。
- 所有新增 OpenSpec 文档和用户可见错误使用简体中文。

---

### Task 1: 共享 Chat contracts 与 OpenAPI

**Files:**
- Create: `packages/api-contracts/src/chat.ts`
- Modify: `packages/api-contracts/src/index.ts`
- Modify: `packages/api-contracts/src/index.test.ts`
- Modify: `packages/api-contracts/contract-manifest.json`
- Modify: `packages/api-contracts/src/openapi.ts`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Modify: `apps/backend/tests/test_api_contracts.py`
- Modify: `apps/backend/tests/test_contract_manifest.py`

**Interfaces:**
- Produces: `ChatRole`, `ChatReference`, `ChatMessageMetadata`, `ChatMessage`, `ChatSession`, `ChatSessionListData`, `ChatSessionDetail`, `AppendChatMessageRequest`, `DeleteChatSessionData`。
- Produces: 六条受保护 Chat OpenAPI operations，统一声明 bearer、401、403，append 额外声明 422。

- [ ] **Step 1: 写 TypeScript 失败合同测试**

在 `packages/api-contracts/src/index.test.ts` 增加手写 fixture，断言 metadata references/toolCallIds、list/detail/create/append/clear/delete DTO 和六条 OpenAPI operation 的精确 path/method/error 集合。

- [ ] **Step 2: 运行 contracts 测试并确认 RED**

Run: `npm run contracts:test`

Expected: FAIL，原因是 Chat exports/OpenAPI paths 尚不存在，而不是测试语法错误。

- [ ] **Step 3: 实现最小 TypeScript contracts 与 manifest**

`chat.ts` 使用 readonly 类型：

```ts
export type ChatRole = "user" | "assistant" | "system" | "tool";

export interface ChatReference {
  readonly chunkId: string;
  readonly documentId: string;
  readonly knowledgeBaseId: string;
  readonly source: string;
  readonly excerpt?: string;
}

export interface ChatMessageMetadata {
  readonly references?: readonly ChatReference[];
  readonly toolCallIds?: readonly string[];
}
```

Session DTO 使用 `id/title/createdAt/updatedAt`；message 使用 `id/sessionId/role/content/sequence/metadata/createdAt`；detail 使用 `{session, messages}`；delete 使用 `{deleted:true, sessionId}`。

- [ ] **Step 4: 写 Python 镜像失败测试并确认 RED**

Run: `cd apps/backend && uv run pytest tests/test_api_contracts.py tests/test_contract_manifest.py -q`

Expected: FAIL，原因是 Pydantic Chat models 或 manifest 镜像缺失。

- [ ] **Step 5: 实现 Pydantic 镜像并跑 GREEN**

Pydantic request 对 `content` 使用 strip 后非空、最大 100000 字符；reference/toolCallIds 每个字符串非空，metadata 默认空对象；alias 使用 camelCase。

Run: `npm run contracts:typecheck && npm run contracts:test && cd apps/backend && uv run pytest tests/test_api_contracts.py tests/test_contract_manifest.py -q`

Expected: PASS。

- [ ] **Step 6: 提交合同边界**

```bash
git add packages/api-contracts apps/backend/src/super_ai/api_contracts.py apps/backend/tests/test_api_contracts.py apps/backend/tests/test_contract_manifest.py
git commit -m "feat: define chat session contracts"
```

### Task 2: Alembic schema、ORM 与 owner-scoped Repository

**Files:**
- Create: `apps/backend/migrations/versions/20260817_0006_manage_chat_sessions.py`
- Create: `apps/backend/src/super_ai/chat/models.py`
- Create: `apps/backend/src/super_ai/chat/repositories.py`
- Create: `apps/backend/src/super_ai/chat/__init__.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/chat_models.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/chat_repositories.py`
- Modify: `apps/backend/src/super_ai/memory/extended_sqlite/__init__.py`
- Modify: `apps/backend/migrations/env.py`
- Create: `apps/backend/tests/chat/conftest.py`
- Create: `apps/backend/tests/chat/test_migration.py`
- Create: `apps/backend/tests/chat/test_repository.py`

**Interfaces:**
- Produces: frozen `ChatSessionRecord`、`ChatMessageRecord`、`ChatMessageMetadataRecord`。
- Produces: `ChatRepository` Protocol 与 `SqliteChatRepository`，方法 `create_session/list_sessions/get_session/get_detail/append_message/clear_messages/delete_session`。

- [ ] **Step 1: 写 migration 与 Repository 失败测试**

测试 fresh upgrade 后两张表、外键、索引、unique sequence、metadata round-trip、UTC 时间、owner-scoped CRUD、稳定排序和 delete cascade。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `cd apps/backend && uv run pytest tests/chat/test_migration.py tests/chat/test_repository.py -q`

Expected: FAIL，原因是 revision、models 和 Repository 尚不存在。

- [ ] **Step 3: 实现迁移和 ORM**

迁移从 `20260813_0005` 继续。`chat_sessions` 建立 `(owner_user_id, updated_at, id)` 索引；`chat_messages` 建立 owner/session/sequence 索引与 `(session_id, sequence)` 唯一约束；两个 owner 外键都指向 users，message session 外键 `ON DELETE CASCADE`。

- [ ] **Step 4: 实现 Repository 最小行为**

所有 SQL 首先约束 `owner_user_id`。列表排序：

```python
.order_by(ChatSessionModel.updated_at.desc(), ChatSessionModel.id.desc())
```

append 在同一 `AsyncSession` 中 owner-scoped 读取父 session、计算 `coalesce(max(sequence), 0) + 1`、flush message、更新 session。JSON 使用现有 `dump_json/load_json` 约定。

- [ ] **Step 5: 运行 Repository GREEN 与静态检查**

Run: `cd apps/backend && uv run pytest tests/chat/test_migration.py tests/chat/test_repository.py -q && uv run ruff check src/super_ai/chat src/super_ai/memory/extended_sqlite/chat_models.py src/super_ai/memory/extended_sqlite/chat_repositories.py tests/chat && uv run pyright src/super_ai/chat src/super_ai/memory/extended_sqlite/chat_models.py src/super_ai/memory/extended_sqlite/chat_repositories.py`

Expected: PASS，0 warning/error。

- [ ] **Step 6: 提交持久化边界**

```bash
git add apps/backend/migrations apps/backend/src/super_ai/chat apps/backend/src/super_ai/memory/extended_sqlite apps/backend/tests/chat
git commit -m "feat: add owner scoped chat persistence"
```

### Task 3: ChatService、事务语义与 FastAPI API

**Files:**
- Create: `apps/backend/src/super_ai/chat/service.py`
- Create: `apps/backend/src/super_ai/chat/dependencies.py`
- Create: `apps/backend/src/super_ai/chat/router.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Create: `apps/backend/tests/chat/test_service.py`
- Create: `apps/backend/tests/chat/test_api.py`
- Modify: `apps/backend/tests/test_app.py`

**Interfaces:**
- Produces: `ChatService.create/list/detail/append/clear/delete`。
- Produces: 六条 `/chat/sessions` API，全部统一 envelope/request-id/bearer/401/403。

- [ ] **Step 1: 写标题、事务和 API 失败测试**

测试第一条 user 消息空白折叠与 48 字符标题；assistant 在前不生成标题；后续 user 不覆盖标题；append 失败时 message/session touch 同时回滚；clear 恢复“新会话”和 sequence 1；两个用户跨 tenant 及随机不存在 ID 都返回相同 `AUTH_FORBIDDEN` 403 envelope。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `cd apps/backend && uv run pytest tests/chat/test_service.py tests/chat/test_api.py -q`

Expected: FAIL，原因是 service/router 尚不存在。

- [ ] **Step 3: 实现最小 ChatService**

标题函数：

```python
def derive_chat_title(content: str) -> str:
    normalized = " ".join(content.split())
    return normalized[:48] or "新会话"
```

Service 在 Repository 返回 `None` 时统一抛出 `AppError("AUTH_FORBIDDEN")`，禁止发起无 scope 存在性查询。

- [ ] **Step 4: 实现依赖和 router**

`get_chat_service` 复用请求级 `get_session`；router 将 record 转换为 Pydantic models，201 只用于创建 session/message，clear/delete 返回 200。

- [ ] **Step 5: 验证 GREEN 和完整事务回滚**

Run: `cd apps/backend && uv run pytest tests/chat -q && uv run ruff check src/super_ai/chat tests/chat && uv run pyright src/super_ai/chat`

Expected: PASS；故障注入后数据库中既没有新 message，也没有错误的 updatedAt/title。

- [ ] **Step 6: 提交 API**

```bash
git add apps/backend/src/super_ai/chat apps/backend/src/super_ai/app.py apps/backend/tests/chat apps/backend/tests/test_app.py
git commit -m "feat: add chat session api"
```

### Task 4: 前端 typed chatClient 与受保护 store

**Files:**
- Create: `apps/frontend/src/chat/chatClient.ts`
- Create: `apps/frontend/src/chat/chatClient.test.ts`
- Create: `apps/frontend/src/stores/chat.ts`
- Create: `apps/frontend/src/stores/chat.test.ts`

**Interfaces:**
- Produces: `ChatClient` 的 list/create/get/append/clear/delete 方法。
- Produces: `useChatStore`，状态为 sessions、selectedSessionId、selectedDetail、loading、errorMessage。

- [ ] **Step 1: 写 client/store 失败测试**

client 测试手写统一 envelope fixture 并断言六条 URL/method/body；store 测试断言初始化、选择详情、create/append/clear/delete 后使用服务端 DTO 对账，401/logout cleanup 清空全部状态，localStorage 除认证 token 外不新增 key。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `npm run test --workspace @super-ai/frontend -- src/chat/chatClient.test.ts src/stores/chat.test.ts`

Expected: FAIL，原因是 client/store 不存在。

- [ ] **Step 3: 实现 typed client**

所有调用委托现有 `ApiClient`，不复制 envelope、error 或 DTO，不访问 localStorage。

- [ ] **Step 4: 实现受保护 store**

store 注册 `registerProtectedStoreCleanup(reset)`；所有 mutation 以服务器响应为事实来源。delete 后重新读取列表，clear 后使用返回 detail，append 后刷新 detail 和列表。

- [ ] **Step 5: 运行前端 GREEN**

Run: `npm run frontend:typecheck && npm run frontend:test && npm run frontend:build`

Expected: PASS。

- [ ] **Step 6: 提交前端基础**

```bash
git add apps/frontend/src/chat apps/frontend/src/stores/chat.ts apps/frontend/src/stores/chat.test.ts
git commit -m "feat: add server backed chat store"
```

### Task 5: OpenSpec 验证、完整门禁与归档

**Files:**
- Modify: `openspec/changes/manage-chat-sessions/tasks.md`
- Create after sync: `openspec/specs/chat-session-management/spec.md`
- Archive: `openspec/changes/archive/2026-08-17-manage-chat-sessions/`

**Interfaces:**
- Consumes: 前四个任务的 contracts、迁移、API 和前端基础。
- Produces: 已验证、已同步、已归档的 P14 change。

- [ ] **Step 1: 运行数据库与 backend 全门禁**

Run: `cd apps/backend && uv run alembic upgrade head && uv run ruff check . && uv run pyright && uv run pytest`

Expected: exit 0，全部测试通过。

- [ ] **Step 2: 运行 contracts/frontend 门禁**

Run: `npm run contracts:typecheck && npm run contracts:test && npm run frontend:typecheck && npm run frontend:test && npm run frontend:build`

Expected: exit 0。

- [ ] **Step 3: 运行仓库门禁**

Run: `openspec validate --all && git diff --check`

Expected: OpenSpec 0 failed，Git whitespace 0 error。

- [ ] **Step 4: 使用 openspec-verify-change 逐项核对**

对每个 requirement 和 scenario 建立实现/测试映射；任何 CRITICAL 先按 TDD 增加失败测试、修复并重跑完整门禁，WARNING 必须处理或给出有证据的处置结论。

- [ ] **Step 5: 同步 delta specs 并归档**

智能合并 `chat-session-management` delta 到主规格，运行 `openspec validate --specs`，确认幂等后归档到日期目录，再运行 `openspec validate --all` 与 `git diff --check`。
