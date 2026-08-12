## Why

现有配置骨架只保存未校验的 `llm.apiKey`，后续 Agent、知识检索和 AIOps 若各自创建模型 client，会产生参数漂移、环境变量依赖、导入联网和异常泄密风险。P06 在产品功能接入前建立统一、可注入且默认安全的 Qwen/百炼 chat、embedding、rerank 边界。

## What Changes

- 完善 P01 本地 JSON 深合并加载器，为文件缺失、非法 JSON 和非对象顶层提供不泄露内容的明确错误，并为 `llm` 与 `modelCapabilities` 增加 Pydantic v2 typed validation。
- 扩展项目与用户配置模板，预留最终 `app`、`backend`、`frontend`、`llm`、`modelCapabilities`、`vectorStore`、`mcp`、`clsMcpServer`、`prometheusAlerts`、`clsLogUpload`、`aiopsDemo` 等 section；所有 credential 模板值保持为空。
- 新增 `LlmProvider` Protocol 与 `QwenOpenAIProvider`：chat 只构造 `ChatOpenAI`，embedding 只构造 `OpenAIEmbeddings`，不引入 DashScope SDK。
- 固化默认 chat profile（`qwen3.7-max`、temperature 0.2、timeout 120 秒、retries 2、显式 context window）和 embedding profile（`text-embedding-v4`、1024 维、原始字符串、禁用 context length 检查、最多 10 条一批并保持顺序）。
- 通过独立可注入异步 HTTP client 调用 `qwen3-vl-rerank`，使用模型专用 endpoint/payload/response，不生成 fallback 分数。
- 提供 chat、embedding、rerank 的最小异步 readiness 探测，返回 provider/model/baseUrl/latency；任何异常中的 API key 都替换为 `[redacted]`。
- 增加 fake transport/config 测试、import-safety 测试和仅供有真实凭据时人工执行的 smoke 指南；未执行 smoke 时不声明通过。
- 本变更不实现 Agent、对话、知识库、向量库写入、检索工具、模型路由、自动 fallback 或 HTTP 产品 endpoint。

## Capabilities

### New Capabilities

- `qwen-model-providers`: 定义本地 typed LLM 配置、Qwen OpenAI-compatible chat/embedding、独立 rerank、readiness、脱敏与导入安全行为。

### Modified Capabilities

- `monorepo-foundation`: 完善本地 JSON 配置错误语义、最终模板 section 和凭据隔离要求。

## Impact

- 后端新增 `super_ai.llm` 包及其配置、provider、rerank、readiness 和测试；继续复用现有 `langchain-openai` 与 `httpx` 依赖，不新增 DashScope SDK。
- `config/project.template.json`、`config/user.project.template.json` 与被忽略的本机配置获得最终 section 骨架；浏览器 public allowlist 不扩大。
- 不新增数据库表、Alembic revision、共享 HTTP/SSE endpoint 或产品 payload；`packages/api-contracts` 只运行回归门禁，不新增临时合同。
