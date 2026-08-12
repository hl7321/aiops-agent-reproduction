# Configure Qwen Model Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 仅通过本地 JSON 深合并配置提供可注入、导入安全且不泄露凭据的 Qwen chat、embedding、rerank 与 readiness 边界。

**Architecture:** `project_config.py` 只负责安全文件/JSON 合并，`super_ai.llm.config` 负责 Pydantic typed settings；`QwenOpenAIProvider` 聚合 ChatOpenAI、OpenAIEmbeddings 和独立 httpx rerank 三个窄边界。所有 client 延迟创建，测试只注入 factory 或 MockTransport。

**Tech Stack:** Python >=3.10、Pydantic v2、langchain-openai 1.x、httpx、pytest/pytest-asyncio、Ruff、strict Pyright、OpenSpec。

## Global Constraints

- 配置只读取显式 `project.json` 与 `user.project.json`，不得读取 OS 环境变量。
- 后端只允许 `from super_ai...`，模块 import 期间不得联网或读取真实配置。
- 禁止引入 DashScope SDK；chat 只使用 ChatOpenAI，embedding 只使用 OpenAIEmbeddings。
- embedding 固定 text-embedding-v4、1024 维、最多 10 条一批并保持顺序。
- rerank 不伪造 fallback 分数；所有 API key 异常文本必须替换为 `[redacted]`。
- 当前工作区含未提交前置变更，本计划不 stage 或 commit。

---

### Task 1: 安全 JSON loader 与模板

**Files:**
- Modify: `apps/backend/src/super_ai/project_config.py`
- Modify: `apps/backend/tests/test_project_config.py`
- Modify: `config/project.template.json`
- Modify: `config/user.project.template.json`
- Modify: `tests/test_repository_policy.py`
- Modify: `apps/frontend/build/public-config.test.ts`

**Interfaces:**
- Produces: `ProjectConfigError(ValueError)`；`load_project_config(project_path: Path, user_path: Path) -> JsonObject`。

- [ ] 写缺失文件、非法 JSON、非 object 顶层的失败测试；预期分别包含路径与安全原因且不含 sentinel 文件内容。
- [ ] 运行 `cd apps/backend && uv run pytest tests/test_project_config.py -q`，确认因错误类型/消息缺失而 RED。
- [ ] 在 `_read_json_object` 捕获 `FileNotFoundError`、`OSError`、`JSONDecodeError` 并转换为 `ProjectConfigError`；保留原 deep merge 行为。
- [ ] 扩展策略测试，递归检查 key/secret/token/password 为空、必需 section/aiopsDemo 字段存在、本机文件被 ignore。
- [ ] 扩展前端 sentinel 测试，把 vectorStore/clsMcpServer/prometheusAlerts/clsLogUpload/aiopsDemo 放入输入并断言 public projection 不含 sentinel。
- [ ] 用模板更新 ignored 的 `config/project.json`，保留 `config/user.project.json` 为本机覆盖且用 `git check-ignore` 验证二者未受追踪。

### Task 2: Typed LLM settings

**Files:**
- Create: `apps/backend/src/super_ai/llm/__init__.py`
- Create: `apps/backend/src/super_ai/llm/config.py`
- Create: `apps/backend/src/super_ai/llm/errors.py`
- Create: `apps/backend/tests/llm/test_config.py`

**Interfaces:**
- Produces: `load_llm_settings(project_path, user_path) -> LlmSettings`。
- Produces: `LlmSettings.require_api_key() -> str`、`capability_for_chat() -> ModelCapability`。
- JSON aliases: `baseUrl`、`timeoutSeconds`、`maxRetries`、`batchSize`、`contextWindowTokens`。

- [ ] 写临时 JSON nested override、缺失 embedding、非法 endpoint、batchSize>10、缺失当前模型 capability、环境变量不生效的失败测试。
- [ ] 运行 `uv run pytest tests/llm/test_config.py -q`，确认模块/行为缺失导致 RED。
- [ ] 实现 frozen/extra-forbid Pydantic models；embedding model/dimension 与 rerank model 使用 Literal，数值使用 `Field` 范围约束。
- [ ] 捕获 `ValidationError`，仅从 `errors()` 的 loc/type 重建 `ModelConfigurationError`，不得拼接 input 或 API key。
- [ ] 运行 targeted tests 并确认 GREEN。

### Task 3: ChatOpenAI 与 embedding 边界

**Files:**
- Create: `apps/backend/src/super_ai/llm/types.py`
- Create: `apps/backend/src/super_ai/llm/provider.py`
- Create: `apps/backend/tests/llm/fakes.py`
- Create: `apps/backend/tests/llm/test_provider.py`
- Create: `apps/backend/tests/llm/test_embedding.py`

**Interfaces:**
- Produces: `LlmProvider` Protocol。
- Produces: `QwenOpenAIProvider.create_chat_model() -> BaseChatModel`。
- Produces: `await QwenOpenAIProvider.embed_documents(texts: Sequence[str]) -> list[list[float]]`。
- 注入：`chat_factory(**kwargs)` 与 `embedding_factory(**kwargs)`。

- [ ] 用捕获参数 factory 写 chat RED 测试，手工断言 model/temperature/timeout/max_retries/base_url/profile.max_input_tokens。
- [ ] 实现 chat factory，显式传入 API key，阻止 langchain-openai 从环境变量 fallback。
- [ ] 写 23 个带索引原始字符串的 embedding RED 测试，fake 按字符串索引返回向量并记录 10/10/3 三批。
- [ ] 实现空输入短路、显式 OpenAIEmbeddings 参数、顺序切片/extend 与每批数量一致性校验。
- [ ] 运行两个 targeted test 文件，确认 GREEN。

### Task 4: qwen3-vl-rerank HTTP adapter

**Files:**
- Create: `apps/backend/src/super_ai/llm/rerank.py`
- Create: `apps/backend/tests/llm/test_rerank.py`

**Interfaces:**
- Produces: immutable `RerankResult(index: int, document: str, relevance_score: float)`。
- Produces: `rerank(client, settings, query, documents, top_n) -> list[RerankResult]`。

- [ ] 用 `httpx.MockTransport` 写 payload/result RED 测试，断言嵌套 query/documents、return_documents=false 和服务端顺序/分数。
- [ ] 写两次 timeout 第三次成功、三次失败、4xx 不重试、malformed index/score、空 documents 短路测试。
- [ ] 实现只重试 TimeoutException/TransportError 的 `maxRetries + 1` 循环；`raise_for_status` 和响应 validation 不伪造结果。
- [ ] 运行 `uv run pytest tests/llm/test_rerank.py -q`，确认 GREEN。

### Task 5: readiness、脱敏和 import safety

**Files:**
- Create: `apps/backend/src/super_ai/llm/readiness.py`
- Create: `apps/backend/tests/llm/test_readiness.py`
- Create: `apps/backend/tests/llm/test_llm_import_safety.py`

**Interfaces:**
- Produces: `ProviderReadiness(provider, model, base_url, latency_ms)`。
- Produces: `await provider.readiness(capability: Literal["chat", "embedding", "rerank"])`。
- Produces: `sanitize_exception(error, api_key) -> ModelProviderError`。

- [ ] 写三个能力的最小调用和 metadata RED 测试；fake chat 捕获 `HumanMessage("ping")`，embedding/rerank 捕获单条输入。
- [ ] 写异常包含两次 sentinel key 的脱敏测试，断言只有 `[redacted]` 且无原 key。
- [ ] 实现 `perf_counter` latency、能力路由和 provider 边界统一异常转换。
- [ ] 用独立子进程 patch socket/client constructors，导入 `super_ai.llm.*` 并断言没有配置读取或网络调用。
- [ ] 运行全部 `tests/llm` 确认 GREEN。

### Task 6: 文档、锁文件和全量门禁

**Files:**
- Modify: `AGENTS.md`
- Modify: `apps/backend/README.md`
- Create: `docs/architecture/model-providers.md`
- Create: `docs/runbooks/qwen-provider-smoke.md`
- Modify: `apps/backend/uv.lock`（由 `uv sync` 维护）

**Interfaces:**
- 文档只声明 provider foundation 已实现；Agent/RAG/真实连通性仍未实现。

- [ ] 运行 `uv sync`，用 `uv tree`/锁文件验证没有 dashscope 包。
- [ ] 写人工 smoke 的本机 JSON 填写、chat/embedding/rerank/readiness 命令与预期；首行明确“未执行，不构成门禁通过证据”。
- [ ] 运行 backend `uv run ruff check .`、`uv run pyright`、`uv run pytest`。
- [ ] 运行 contracts typecheck/test、frontend public-config test/build/secret scan、docs build。
- [ ] 运行 `openspec validate --all` 与 `git diff --check`，然后执行 verify、同步 specs 并归档。
