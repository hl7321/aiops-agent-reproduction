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

## chat 使用独立端点与密钥

`llm.baseUrl` 与 `llm.apiKey` 是 embedding 与 rerank 的端点与凭据。chat 可以在自己的 section 下覆盖它们：

```json
{
  "llm": {
    "provider": "openai-compatible",
    "apiKey": "<百炼 key：embedding 与 rerank 使用>",
    "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "chat": {
      "model": "deepseek-chat",
      "temperature": 0.2,
      "timeoutSeconds": 120,
      "maxRetries": 2,
      "baseUrl": "https://api.deepseek.com/v1",
      "apiKey": "<DeepSeek key：只有 chat 使用>"
    },
    "embedding": { "model": "text-embedding-v4", "dimensions": 1024, "batchSize": 10, "timeoutSeconds": 120, "maxRetries": 2 },
    "rerank": { "model": "qwen3-vl-rerank", "endpoint": "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank", "timeoutSeconds": 120, "maxRetries": 2 }
  },
  "modelCapabilities": {
    "qwen3.7-max": { "contextWindowTokens": 262144 },
    "deepseek-chat": { "contextWindowTokens": 65536 }
  }
}
```

生效规则：

- `chat.baseUrl` / `chat.apiKey` **未配置或为空字符串**时回退到 `llm.baseUrl` / `llm.apiKey`，行为与只配置顶层值完全一致。
- 一旦填了非空值，**只作用于 chat**；embedding 与 rerank 继续使用顶层端点与凭据。DeepSeek 不提供 embedding 服务，所以这两类能力必须留在能提供 embedding 与 rerank 的厂商。
- `apiKey` 填在 `config/user.project.json`（被 git 忽略）里；`baseUrl` 不是密钥，放在 `config/project.json` 即可。
- chat 的异常脱敏使用**本次调用真正用的那把 key**；两把 key 同时存在时都会被替换成 `[redacted]`。
- `provider` 是部署形态标签（会写进 readiness 结果），不再是厂商枚举；默认值仍是 `qwen-openai`。

### 换 chat 模型时要改哪里

1. `llm.chat.model` 改成目标模型 id；
2. `modelCapabilities` 里补一条**与模型同名**的 `contextWindowTokens` 登记——漏了会在创建 client 前直接报错，错误信息会指出要补哪一项；
3. 换了厂商的话，再改 `llm.chat.baseUrl` 与 `llm.chat.apiKey`。

`contextWindowTokens` 影响聊天记忆的压缩阈值：填小了只会提前压缩（更保守），填大了才有超出真实窗口被截断的风险，所以不确定时按偏小的值登记。

## Readiness 与错误

readiness 分别发送最小 chat `ping`、单条 embedding `ping`、单 query/document rerank 请求，成功结果序列化为：

```json
{
  "provider": "配置里的 provider 标签",
  "model": "具体模型名",
  "baseUrl": "调用地址",
  "latency": 0.0
}
```

chat 分支的 `baseUrl` 是 chat 的**生效**端点（配置了覆盖就是覆盖值）。latency 单位为毫秒。任何异常越过 provider 边界前，本次调用涉及的本地 JSON API key 的每次出现都会替换为 `[redacted]`。错误不会附加 Authorization header 或完整配置，也不会生成 embedding/rerank fallback 数据。

## 当前非目标

P06 不实现 Agent、LangGraph graph、聊天 endpoint、RAG、知识库、Milvus 写入、模型路由、自动 fallback 或管理页面。真实百炼 smoke 是需要有效本机凭据且会产生外部请求/费用的人工动作，不属于默认自动化门禁。
