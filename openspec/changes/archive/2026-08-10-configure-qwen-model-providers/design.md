## Context

P01 已提供显式路径 JSON 深合并和前端公开字段投影，P03/P04/P05 已建立运行期依赖注入、认证和 tenant 边界；后端依赖中已有 `langchain-openai>=1,<2` 与 `httpx>=0.27,<1`。当前没有模型 typed settings、provider 或外部模型 client。详见 proposal.md 与两份 delta specs。

百炼 OpenAI-compatible 默认地址使用 `https://dashscope.aliyuncs.com/compatible-mode/v1`；rerank 使用 `https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank`，两者均可由本地 JSON 覆盖为 workspace 专属域名。官方合同确认 `text-embedding-v4` 支持 1024 维且单批最多 10，`qwen3-vl-rerank` 使用独立的嵌套 `input`/`parameters` HTTP 结构。

## Goals / Non-Goals

**Goals：**

- 在不读取环境变量的前提下，把深合并 JSON 转换成不可变 Pydantic v2 typed settings，并安全报告字段错误。
- 让 chat、embedding、rerank 和 readiness 都能注入 fake，且 production client 只在显式调用时构造。
- 固化 Qwen 参数、embedding 批处理顺序、rerank 重试/真实分数和异常脱敏。
- 扩充最终配置模板但不扩大浏览器 allowlist。

**Non-Goals：**

- 不实现 Agent、LangGraph graph、对话、RAG、Milvus 写入、模型自动选择、fallback、流式 endpoint 或管理页面。
- 不增加 DashScope SDK、数据库迁移、产品 API 合同或应用启动时 readiness。
- 自动化测试不连接真实百炼；人工 smoke 不属于自动化通过证据。

## Decisions

### 1. ProjectConfigError 与 typed LlmSettings 分层

`project_config.py` 继续负责文件 I/O、JSON object 归一化和递归深合并，并新增稳定 `ProjectConfigError`。文件不存在、读取失败、JSON decode 和非 object 使用不同安全消息，只包含调用方已经提供的路径，不回显内容。

`super_ai.llm.config` 使用 frozen、`extra="forbid"` 的 Pydantic v2 模型校验 `llm` 与 `modelCapabilities`。字段采用 JSON camelCase alias；API key 使用 `SecretStr`，允许模板中的空值通过结构校验，但任何 client factory 在构造前调用 `require_api_key()` 拒绝空值。validation error 只根据 `errors()` 的 `loc` 与 `type` 重建安全消息，不串接可能包含 input 的原始异常文本。

替代方案是让 project loader 直接返回完整应用 Pydantic model；P06 只拥有 LLM section，提前校验未来尚未实现的 section 会耦合后续提案，因此拒绝。

### 2. 一个 LlmProvider Protocol 聚合三个窄调用面

`LlmProvider` 声明 `create_chat_model()`、`embed_documents()`、`rerank()` 与 `readiness()`；`QwenOpenAIProvider` 持有 typed settings 和可选注入 factory/client。默认 chat factory 唯一构造 `ChatOpenAI`，默认 embedding factory 唯一构造 `OpenAIEmbeddings`，rerank 默认在调用时创建短生命周期 `httpx.AsyncClient`。测试分别注入捕获参数的 factory、embedding fake 与 `httpx.MockTransport`。

替代方案是暴露一个通用 `invoke(kind, payload)`；它会丢失类型、混合不同错误/批处理语义，也鼓励临时 payload，因此拒绝。三个完全独立 provider class 会重复 credential、readiness 和脱敏逻辑，本阶段也不需要。

### 3. chat 参数和 capability profile 都来自 typed config

模板默认 `qwen3.7-max`、temperature 0.2、timeout 120、maxRetries 2，并在 `modelCapabilities.qwen3.7-max.contextWindowTokens` 记录 262144。settings 跨字段校验确保当前 chat model 一定存在 profile；factory 同时把 context window 转成 LangChain profile 的 `max_input_tokens`，provider 另提供 typed capability 供后续 token budget 使用。

替代方案是在代码中按模型名维护隐藏常量；它会让切换模型时配置与实际能力漂移，因此拒绝。

### 4. embedding 由 provider 显式分批

`OpenAIEmbeddings` 参数固定 model `text-embedding-v4`、dimensions 1024、`check_embedding_ctx_length=False`，chunk_size 使用配置且限制 1..10。`embed_documents()` 接受 `Sequence[str]`，先复制为原始字符串 list，再按 batchSize 顺序切片并逐批 `aembed_documents()`，依次 extend 结果；每批向量数量不等于输入数量时立即失败。空输入在构造 client 前返回空列表。

依赖库自身也支持 chunk_size，但显式分批才能用 fake 精确证明每次不超过 10、原始文本未被 token 化或改写以及跨批顺序稳定。

### 5. rerank 直接实现 qwen3-vl-rerank HTTP 合同

请求体为：

```json
{
  "model": "qwen3-vl-rerank",
  "input": {"query": {"text": "..."}, "documents": [{"text": "..."}]},
  "parameters": {"return_documents": false, "top_n": 2}
}
```

Authorization 使用同一 `llm.apiKey`。只对 `httpx.TimeoutException` 和 `httpx.TransportError` 重试，`maxRetries=2` 表示初次加两次重试；4xx/5xx 不重试。响应必须具有 `output.results[].index/relevance_score`，index 唯一且在原 documents 范围内，最终 record 保留服务端顺序和真实分数。空 documents 直接返回空结果，不创建 HTTP client；不存在 fallback。

### 6. readiness 复用公开调用路径并在单一出口脱敏

readiness 的 chat 输入为单条 `HumanMessage("ping")`，embedding 输入为 `"ping"`，rerank 输入为 query/document 各一条和 top_n 1。`time.perf_counter()` 计算毫秒 latency。成功 record 返回 provider=`qwen-openai`、具体模型、公开 base URL 与非负 latency。

所有 provider 外部异常通过 `sanitize_exception(error, api_key)` 转为 `ModelProviderError`；函数用精确 key 全量替换 `[redacted]`，不附加 headers/config。配置 validation 在 key 变成异常 input 前先单独脱敏。

替代方案是仅依赖 SDK 的 SecretStr repr；HTTP 异常和服务端 message 仍可能回显 key，因此必须设置统一出口。

### 7. 模块 import 保持纯声明

`super_ai.llm` 的模块级内容只包含模型、Protocol、函数与默认常量；不读取 `config/*.json`，不实例化 ChatOpenAI/OpenAIEmbeddings/AsyncClient，也不执行 readiness。应用或后续 dependency provider 显式传入 `LlmSettings` 后才创建 `QwenOpenAIProvider`。

## Risks / Trade-offs

- **workspace 专属域名可能替代公共域名** → base URL 和 rerank endpoint 均在本地 JSON 可覆盖，人工 smoke 指南要求按百炼控制台填写。
- **顺序分批降低 embedding 并发吞吐** → P06 优先保证限额与确定性；后续性能 change 可在保持索引重排的前提下增加受控并发。
- **readiness 会产生最小模型费用** → 只由显式运维/诊断调用触发，不在 import 或应用启动时自动运行。
- **只按精确 API key 脱敏无法识别未知第三方秘密** → provider 不把 headers/config 加入错误，后续统一日志提案仍需结构化敏感字段策略。
- **qwen3-vl-rerank 支持多模态但本阶段只接受文本** → 保持与当前知识文本基础一致；图片/视频合同由后续多模态 change 扩展。

## Migration Plan

1. 先扩展 loader 测试和模板；把当前被忽略的 `project.json` 从新模板复制，`user.project.json` 保留本机覆盖且不 stage。
2. 增加 typed settings 与 fake-based RED 测试，再实现 provider、rerank、readiness 和 import-safety。
3. 运行 `uv sync` 更新锁文件；确认依赖图不存在 DashScope SDK。
4. 更新后端 README/架构文档与人工 smoke 指南，声明 smoke 尚未执行。
5. 完整门禁、verify、主规格同步后归档。回滚只移除 `super_ai.llm` 和新增配置字段；数据库及现有认证数据不变。
