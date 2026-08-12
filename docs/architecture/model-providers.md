# 模型 Provider 架构

## 配置来源

模型配置只由显式传入的 `config/project.json` 与 `config/user.project.json` 递归深合并产生。`super_ai.project_config` 负责安全文件/JSON 错误，`super_ai.llm.config` 只校验 `llm` 和 `modelCapabilities`。应用不得从 OS 环境变量补取 API key；模板允许空 key，任何 client factory 会在显式调用前拒绝空值。

浏览器 public config allowlist 没有扩大。`llm`、`modelCapabilities`、`vectorStore`、`clsMcpServer`、`prometheusAlerts`、`clsLogUpload` 与 `aiopsDemo` 均为服务端配置，不能进入前端 bundle。

## 注入边界

- `LlmProvider`：统一声明 chat、embedding、rerank 与 readiness 行为。
- `QwenOpenAIProvider.create_chat_model()`：显式创建 `ChatOpenAI`，默认 qwen3.7-max、temperature 0.2、timeout 120 秒、max retries 2；能力 profile 的 context window 来自 `modelCapabilities`。
- `QwenOpenAIProvider.embed_documents()`：显式创建 `OpenAIEmbeddings`，固定 text-embedding-v4、1024 维、关闭 client 侧 context token 化检查。输入按最多 10 条顺序分批，空输入不创建 client。
- `QwenOpenAIProvider.rerank()`：使用独立 `httpx.AsyncClient` 调用 qwen3-vl-rerank endpoint。只对 timeout/transport 错误执行配置次数的 retry，结果必须使用服务端真实 index/score。

production 默认 factory 只在上述方法被调用时构造 client。测试可注入 chat/embedding factory 或 `httpx.MockTransport`，模块 import 不读取配置、不构造 client、不连接网络。

## Readiness 与错误

readiness 分别发送最小 chat `ping`、单条 embedding `ping`、单 query/document rerank 请求，成功结果序列化为：

```json
{
  "provider": "qwen-openai",
  "model": "具体模型名",
  "baseUrl": "调用地址",
  "latency": 0.0
}
```

latency 单位为毫秒。任何异常越过 provider 边界前，当前本地 JSON API key 的每次出现都会替换为 `[redacted]`。错误不会附加 Authorization header 或完整配置，也不会生成 embedding/rerank fallback 数据。

## 当前非目标

P06 不实现 Agent、LangGraph graph、聊天 endpoint、RAG、知识库、Milvus 写入、模型路由、自动 fallback 或管理页面。真实百炼 smoke 是需要有效本机凭据且会产生外部请求/费用的人工动作，不属于默认自动化门禁。
