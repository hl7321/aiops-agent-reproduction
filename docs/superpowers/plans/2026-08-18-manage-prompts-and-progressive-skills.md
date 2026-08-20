# Prompt 与 Progressive Skill 管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立每用户 Prompt/Skill 资产、选择配置和只在模型真实调用时读取 `SKILL.md` 正文的 progressive Agent 装配。

**Architecture:** 三张 owner-scoped SQLite 表保存 configuration、Prompt 和 Skill；HTTP service 原子管理选择与 fallback。每轮 Chat 创建 frozen 配置快照，system prompt 只包含平台规则、当前 Prompt 与选中 Skill 摘要，请求级 `load_skill` 再用 owner+allowlist 双重约束延迟读取正文。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、PyYAML safe_load、LangChain 1.x create_agent、TypeScript 5.6 strict、Pinia 3、Vitest 2、pytest。

## Global Constraints

- 后端只允许 `from super_ai...`，模块 import 不读取本机配置、不连接 SQLite、Milvus、LLM 或 MCP。
- 所有 Repository 方法把 `owner_user_id` 作为首个业务参数；跨 owner 直接资源与不存在复用安全 404。
- Skill 文件名严格为 `SKILL.md`，UTF-8 且不超过 256 KiB；name 最多 64 字符，description 最多 500 字符，summary 最多 240 字符。
- 初始 system prompt 不得包含 Skill 正文；用户 Prompt 不得改变 CurrentUser、tenant filter 或可信工具实现。
- Prompt、Skill 与选择不写 localStorage；P16 不实现 P19 最终侧栏。
- 当前工作树包含未整体提交的 P13/P15 文件；实施阶段不自动 commit 或 stage 混合文件，除非用户另行授权。

---

## File Structure

- `packages/api-contracts/src/chat-configuration.ts`：Prompt/Skill/configuration DTO 与上传 policy。
- `apps/backend/src/super_ai/chat_configuration/models.py`：不可变 records 与 parsed Skill 类型。
- `apps/backend/src/super_ai/chat_configuration/repositories.py`：Repository Protocol。
- `apps/backend/src/super_ai/chat_configuration/parser.py`：`SKILL.md` 安全解析与 name 规范化。
- `apps/backend/src/super_ai/chat_configuration/service.py`：CRUD、原子选择与 fallback。
- `apps/backend/src/super_ai/chat_configuration/assembly.py`：frozen snapshot 与 system prompt 组装。
- `apps/backend/src/super_ai/chat_configuration/tools.py`：请求级 `load_skill` Tool。
- `apps/backend/src/super_ai/chat_configuration/router.py`、`dependencies.py`：HTTP/DI。
- `apps/backend/src/super_ai/memory/extended_sqlite/chat_configuration_models.py`、`chat_configuration_repositories.py`：SQLite adapter。
- `apps/frontend/src/chat/configurationClient.ts`、`apps/frontend/src/stores/chatConfiguration.ts`：typed transport 与 protected state。

### Task 1: Contracts 与 OpenAPI

**Files:**
- Create: `packages/api-contracts/src/chat-configuration.ts`
- Modify: `packages/api-contracts/src/index.ts`
- Modify: `packages/api-contracts/contract-manifest.json`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Test: `packages/api-contracts/src/chat-configuration.test.ts`
- Test: `apps/backend/tests/test_contract_manifest.py`

**Interfaces:**
- Produces: `ChatPrompt`、`ChatSkill`、`ChatConfigurationData`、`UpdateChatConfigurationRequest`、`CreateChatPromptRequest`、`UpdateChatPromptRequest`、`ChatAssetDeleteData`、`CHAT_SKILL_UPLOAD_POLICY`。

- [ ] **Step 1: 写 contracts RED 测试**

```ts
expect(CHAT_SKILL_UPLOAD_POLICY).toEqual({
  multipart: { file: "file" }, filename: "SKILL.md", maxBytes: 262144,
  maxNameCharacters: 64, maxDescriptionCharacters: 500, maxSummaryCharacters: 240,
});
expect(chatConfigurationOperations).toHaveLength(7);
```

- [ ] **Step 2: 运行 RED**

Run: `npm run contracts:test -- --run src/chat-configuration.test.ts`
Expected: FAIL，因为导出与 operations 尚不存在。

- [ ] **Step 3: 实现共享类型、manifest 和 Python 镜像**

```ts
export interface UpdateChatConfigurationRequest {
  readonly selectedPromptId: string | null;
  readonly selectedSkillIds: readonly string[];
}
```

七个 operation 使用 `BearerAuth`，GET/PUT configuration 与 Prompt/Skill CRUD 复用统一 envelope；上传声明 multipart、409 与 validation。

- [ ] **Step 4: 运行 GREEN**

Run: `npm run contracts:typecheck && npm run contracts:test && cd apps/backend && uv run pytest tests/test_contract_manifest.py -q`
Expected: PASS。

### Task 2: Migration 与 Repository

**Files:**
- Create: `apps/backend/migrations/versions/20260818_0008_add_chat_prompt_skills.py`
- Create: `apps/backend/src/super_ai/chat_configuration/models.py`
- Create: `apps/backend/src/super_ai/chat_configuration/repositories.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/chat_configuration_models.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/chat_configuration_repositories.py`
- Modify: `apps/backend/migrations/env.py`
- Test: `apps/backend/tests/chat_configuration/test_migration_and_repository.py`

**Interfaces:**
- Produces: `ChatPromptRecord`、`ChatSkillRecord`、`ChatConfigurationRecord` 与 `SqliteChatConfigurationRepository`。
- Repository core: `get(owner_user_id)`、`create_prompt(owner_user_id, ...)`、`update_prompt(owner_user_id, id, ...)`、`delete_prompt(owner_user_id, id)`、`create_skill(owner_user_id, parsed)`、`delete_skill(owner_user_id, id)`、`replace_selection(owner_user_id, prompt_id, skill_ids)`、`get_skill_content(owner_user_id, normalized_name)`。

- [ ] **Step 1: 写 migration/Repository RED 测试**

```python
assert table_names == {
    "user_chat_configurations", "user_chat_prompts", "user_chat_skills"
}
assert await repository.update_prompt("user-b", prompt_a.id, "x", "y") is None
```

测试同 owner name 唯一、不同 owner 同名、稳定排序和 records frozen。

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/chat_configuration/test_migration_and_repository.py -q`
Expected: FAIL，因为 revision/models/repository 不存在。

- [ ] **Step 3: 实现三表与 adapter**

```python
class ChatConfigurationRecord(NamedTuple):
    selected_prompt_id: str | None
    prompts: tuple[ChatPromptRecord, ...]
    skills: tuple[ChatSkillRecord, ...]
```

所有 SQL 条件同时包含 owner 与目标 id；`replace_selection` 先校验完整目标集合，再批量更新 `is_selected`。

- [ ] **Step 4: 运行 GREEN 与 migration gate**

Run: `cd apps/backend && uv run alembic upgrade head && uv run pytest tests/chat_configuration/test_migration_and_repository.py -q`
Expected: PASS，head 为 `20260818_0008`。

### Task 3: SKILL.md Parser 与示例

**Files:**
- Modify: `apps/backend/pyproject.toml`
- Modify: `apps/backend/uv.lock`
- Create: `apps/backend/src/super_ai/chat_configuration/parser.py`
- Create: `docs/examples/skills/knowledge-search/SKILL.md`
- Create: `docs/examples/skills/log-analysis/SKILL.md`
- Create: `docs/examples/skills/incident-report/SKILL.md`
- Create: `docs/examples/skills/api-troubleshooting/SKILL.md`
- Create: `docs/examples/skills/change-risk-review/SKILL.md`
- Test: `apps/backend/tests/chat_configuration/test_skill_parser.py`
- Test: `apps/backend/tests/chat_configuration/test_standard_skills.py`

**Interfaces:**
- Produces: `normalize_skill_name(value: str) -> str`、`parse_skill_document(filename: str, payload: bytes) -> ParsedSkillDocument`。

- [ ] **Step 1: 写 parser RED 表驱动测试**

```python
@pytest.mark.parametrize("filename", ["skill.md", "folder/SKILL.md", "SKILL.MD"])
def test_parser_rejects_non_exact_filename(filename: str) -> None:
    with pytest.raises(SkillDocumentValidationError):
        parse_skill_document(filename, VALID_SKILL)
```

再覆盖非 UTF-8、超限、无 frontmatter、非 object、YAML date、空 description 与 name 规范化。

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/chat_configuration/test_skill_parser.py -q`
Expected: FAIL，因为 parser 不存在。

- [ ] **Step 3: 添加 PyYAML 并实现 safe parser**

```python
metadata = yaml.safe_load(frontmatter)
json.dumps(metadata, ensure_ascii=False, allow_nan=False)
```

只接受 JSON-safe primitive/list/dict；summary 为规范化 description 的前 240 字符。

- [ ] **Step 4: 创建并验证五个示例**

每个 frontmatter name 与目录一致，description 说明用途，正文给出可执行步骤但不包含凭据。

Run: `cd apps/backend && uv sync && uv run pytest tests/chat_configuration/test_skill_parser.py tests/chat_configuration/test_standard_skills.py -q`
Expected: PASS。

### Task 4: Service 与 HTTP API

**Files:**
- Create: `apps/backend/src/super_ai/chat_configuration/service.py`
- Create: `apps/backend/src/super_ai/chat_configuration/router.py`
- Create: `apps/backend/src/super_ai/chat_configuration/dependencies.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Test: `apps/backend/tests/chat_configuration/test_service.py`
- Test: `apps/backend/tests/chat_configuration/test_api.py`

**Interfaces:**
- Consumes: contracts、parser 与 Repository。
- Produces: `ChatConfigurationService` 的 get/update/create/update/delete/upload operations，所有 route 返回共享 envelope。

- [ ] **Step 1: 写 service/API RED 测试**

```python
response = await client.put(
    "/chat/configuration",
    headers=auth_a,
    json={"selectedPromptId": prompt_a, "selectedSkillIds": [skill_a, foreign_skill]},
)
assert response.status_code == 404
assert (await get_configuration(client, auth_a))["selectedSkillIds"] == []
```

覆盖 Prompt 删除 fallback、Skill FormData、409、401、requestId 和跨 owner。

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/chat_configuration/test_service.py tests/chat_configuration/test_api.py -q`
Expected: FAIL，因为 router/service 未实现。

- [ ] **Step 3: 实现 service/router/DI**

```python
@router.post("/skills", response_model=SuccessEnvelope[ChatConfigurationData])
async def upload_skill(file: Annotated[UploadFile, File()], ...): ...
```

读取最多 `262145` bytes 以识别超限；解析完成后才打开写事务。

- [ ] **Step 4: 运行 GREEN**

Run: `cd apps/backend && uv run pytest tests/chat_configuration tests/test_app.py tests/test_contract_manifest.py -q`
Expected: PASS。

### Task 5: Progressive Agent 装配

**Files:**
- Create: `apps/backend/src/super_ai/chat_configuration/assembly.py`
- Create: `apps/backend/src/super_ai/chat_configuration/tools.py`
- Modify: `apps/backend/src/super_ai/chat/agent_runner.py`
- Modify: `apps/backend/src/super_ai/chat/agent_tools.py`
- Modify: `apps/backend/src/super_ai/chat/dependencies.py`
- Test: `apps/backend/tests/chat_configuration/test_assembly.py`
- Test: `apps/backend/tests/chat_configuration/test_load_skill_tool.py`
- Modify: `apps/backend/tests/chat/test_agent_runner.py`
- Modify: `apps/backend/tests/chat/test_stream_service.py`

**Interfaces:**
- Produces: `ChatAgentConfigurationSnapshot`、`assemble_system_prompt(snapshot)`、`create_load_skill_tool(current_user, allowed_names, loader)`。
- Changes: `AgentChatRunner(..., system_prompt: str)` and `AgentFactory(model, tools, system_prompt)`。

- [ ] **Step 1: 写 assembler RED 测试**

```python
prompt = assemble_system_prompt(snapshot_with(content="SKILL_BODY_SENTINEL"))
assert "knowledge-search" in prompt
assert "检索知识库" in prompt
assert "SKILL_BODY_SENTINEL" not in prompt
assert prompt.index("平台安全规则") < prompt.index("用户 Prompt")
```

- [ ] **Step 2: 写 load_skill RED 测试**

```python
result = await tool.ainvoke({"name": "Knowledge Search"})
assert result["content"] == "SKILL_BODY_SENTINEL"
with pytest.raises(SkillNotAvailableError):
    await tool.ainvoke({"name": "other-user-skill"})
```

fake loader 记录正文读取次数；模型不调用时必须为 0。

- [ ] **Step 3: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/chat_configuration/test_assembly.py tests/chat_configuration/test_load_skill_tool.py -q`
Expected: FAIL，因为 snapshot/assembler/tool 不存在。

- [ ] **Step 4: 实现快照、assembler 与 Tool**

```python
if normalized_name not in allowed_names:
    raise SkillNotAvailableError("该 Skill 未在本轮选择")
return await loader.load(current_user.owner_user_id, normalized_name)
```

loader 每次用独立 session 按 owner+name 读取；日志不得包含 content。

- [ ] **Step 5: 接入 create_agent 并运行 GREEN**

`_create_agent` 使用传入的 `system_prompt`，dependencies 每轮先读取 snapshot，再创建 knowledge/time/load_skill 三类工具。

Run: `cd apps/backend && uv run pytest tests/chat tests/chat_configuration/test_assembly.py tests/chat_configuration/test_load_skill_tool.py -q`
Expected: PASS，existing reasoning/reference/audit tests 无回归。

### Task 6: Frontend Client 与 Store

**Files:**
- Create: `apps/frontend/src/chat/configurationClient.ts`
- Create: `apps/frontend/src/chat/configurationClient.test.ts`
- Create: `apps/frontend/src/stores/chatConfiguration.ts`
- Create: `apps/frontend/src/stores/chatConfiguration.test.ts`

**Interfaces:**
- Produces: `ChatConfigurationClient` 七个 methods 与 `createChatConfigurationStore({client})`。

- [ ] **Step 1: 写 client/store RED 测试**

```ts
const form = new FormData();
form.set(CHAT_SKILL_UPLOAD_POLICY.multipart.file, file);
await client.uploadSkill(file);
expect(fetchBody).toBeInstanceOf(FormData);
```

store 测试初始化、PUT 选择、Prompt CRUD、Skill 删除、401 cleanup，且 storage fake 的 `setItem` 从未接收领域数据。

- [ ] **Step 2: 运行 RED**

Run: `npm run frontend:test -- --run src/chat/configurationClient.test.ts src/stores/chatConfiguration.test.ts`
Expected: FAIL，因为 client/store 不存在。

- [ ] **Step 3: 实现 typed client/store**

所有请求直接使用共享 DTO；每个写 action 成功后调用 `applyConfiguration(response.data)`，并注册 `registerProtectedStoreCleanup(reset)`。

- [ ] **Step 4: 运行 GREEN**

Run: `npm run frontend:typecheck && npm run frontend:test -- --run src/chat/configurationClient.test.ts src/stores/chatConfiguration.test.ts`
Expected: PASS。

### Task 7: Full Gates、真实 Smoke、Verify 与 Archive

**Files:**
- Create: `docs/runbooks/prompt-progressive-skills-smoke.md`
- Update: `openspec/changes/manage-prompts-and-progressive-skills/tasks.md`
- Sync: `openspec/specs/prompt-and-progressive-skill-management/spec.md`
- Sync: `openspec/specs/agentic-rag-chat-streaming/spec.md`
- Sync: `openspec/specs/api-and-sse-contracts/spec.md`

**Interfaces:**
- Produces: 完整门禁证据、真实/未执行 smoke 记录、verify 报告与归档 change。

- [ ] **Step 1: 运行后端完整门禁**

Run: `cd apps/backend && uv sync && uv run alembic upgrade head && uv run ruff check . && uv run pyright && uv run pytest`
Expected: 全部 exit 0。

- [ ] **Step 2: 运行 contracts/frontend/repository 门禁**

Run: `npm run contracts:typecheck && npm run contracts:test && npm run frontend:typecheck && npm run frontend:test && npm run frontend:build && npm run frontend:test:secret && openspec validate --all && git diff --check`
Expected: 全部 exit 0，浏览器 bundle 不含 injected secret。

- [ ] **Step 3: 执行真实 Qwen progressive smoke**

创建一次性用户，上传并选中带正文 sentinel 的 Skill，发送明确需要该 Skill 的问题；验证初始 prompt 证据不含正文、真实 audit 出现 `load_skill completed`、assistant 完整保存。清理一次性账号并停止本轮启动的服务。无有效凭据时在 runbook 写“未执行”。

- [ ] **Step 4: 执行 OpenSpec verify**

按 requirement/scenario 映射代码与测试；修复所有 CRITICAL，处理 WARNING 后重跑受影响门禁并勾选 7.4。

- [ ] **Step 5: 同步与归档**

智能合并三个 delta specs，运行 `openspec validate --specs`，确认无差异后移动至 `openspec/changes/archive/2026-08-18-manage-prompts-and-progressive-skills`，最后验证 `openspec list --json` 无 active P16。
