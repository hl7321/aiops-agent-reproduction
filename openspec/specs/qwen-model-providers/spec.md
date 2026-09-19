# Qwen Model Providers 规格

## Purpose

本能力为后续 Agent、知识检索和 AIOps 提供可注入、可测试且默认不泄露凭据的 Qwen/百炼模型访问边界，并在产品功能实现前统一 chat、embedding、rerank 与 readiness 的行为合同。
## Requirements
### Requirement: 模型配置只来自本地 JSON 合并结果

模型 provider SHALL 只消费显式传入的项目配置与用户配置递归深合并结果，MUST NOT 读取 OS 环境变量作为项目配置来源。`llm` 与 `modelCapabilities` MUST 通过 typed validation；缺失字段、非法 URL、无效数值或 chat model 缺少 capability profile 时 MUST 在创建外部 client 前返回安全、可定位且不包含 API key 的配置错误。`llm.provider` MUST 是非空字符串标签，用于在 readiness 结果里标识这份配置的部署形态；MUST NOT 被限制为固定厂商枚举，因为 chat 与 embedding/rerank 可以来自不同厂商。

#### Scenario: 用户配置覆盖嵌套模型值
- **WHEN** 项目配置声明默认 chat 参数而用户配置只覆盖模型名或 API key
- **THEN** typed settings 使用覆盖值并保留未覆盖的默认参数与 capability profile

#### Scenario: 模型配置缺少必填字段
- **WHEN** 合并结果缺少 `llm.embedding`、rerank endpoint 或当前 chat model 的 `contextWindowTokens`
- **THEN** validation 在创建任何外部 client 前失败并指出字段路径，且错误不包含 API key

#### Scenario: chat 模型未登记 capability
- **WHEN** 合并结果的 `llm.chat.model` 在 `modelCapabilities` 中没有同名条目
- **THEN** 配置错误指出需要补齐 `modelCapabilities.<模型名>.contextWindowTokens`，使换模型的人知道要改哪里

#### Scenario: OS 环境变量包含不同凭据
- **WHEN** 进程环境存在模型 API key 但显式 JSON 配置未提供可用 key
- **THEN** provider 不采用环境变量值并在显式调用时返回缺少本地凭据的安全错误

### Requirement: 三类模型能力使用可注入边界
系统 SHALL 提供统一模型 provider 合同以及 chat、embedding、rerank 三类可替换调用边界。Qwen 实现 MUST 使用 OpenAI-compatible chat 与 embedding client，并使用独立异步 HTTP client 调用 rerank；MUST NOT 依赖 DashScope SDK。外部 client MUST 只在 factory 或显式调用路径创建。

#### Scenario: 注入受控 client
- **WHEN** 测试向 Qwen provider 注入 chat、embedding 或 HTTP fake transport
- **THEN** provider 通过相同公开合同执行且不连接真实百炼服务

#### Scenario: 检查依赖边界
- **WHEN** 审查或安装后端依赖
- **THEN** chat/embedding 由既定 OpenAI-compatible 库提供，rerank 使用 HTTP client，且不存在 DashScope SDK

### Requirement: chat 使用可配置能力 profile

chat client SHALL 使用可配置模型，默认 `qwen3.7-max`、temperature `0.2`、timeout `120` 秒、max retries `2`。当前 chat model MUST 在 `modelCapabilities` 中提供正整数 `contextWindowTokens`，并随 client/profile 暴露给后续调用方。chat SHALL 支持独立的 `baseUrl` 与 `apiKey` 覆盖：两者都是可选字段，未提供或为空字符串时 MUST 回退到 `llm.baseUrl` / `llm.apiKey`，提供非空值时 MUST 只作用于 chat，MUST NOT 改变 embedding 与 rerank 的端点或凭据。非空 `baseUrl` MUST 是 http/https 且不含凭据的 URL。

#### Scenario: 创建默认 chat client
- **WHEN** 使用模板默认值显式创建 chat client
- **THEN** client 获得 `qwen3.7-max`、0.2 temperature、120 秒 timeout、2 次 retry、配置 base URL 和对应 context window

#### Scenario: 切换有 profile 的 chat model
- **WHEN** 用户配置覆盖 chat model 且为新模型提供 `contextWindowTokens`
- **THEN** provider 使用新模型和匹配的能力 profile，不修改其他默认参数

#### Scenario: chat 使用独立端点与密钥
- **WHEN** 用户为 chat 提供独立的 `baseUrl` 与 `apiKey`，同时保留顶层 `llm.baseUrl` 与 `llm.apiKey`
- **THEN** chat client 使用 chat 自己的端点与密钥，而 embedding 与 rerank 继续使用顶层端点与密钥

#### Scenario: chat 覆盖字段留空
- **WHEN** chat 的 `baseUrl` 或 `apiKey` 是空字符串
- **THEN** 该字段视为未提供并回退到顶层值，行为与只配置顶层值完全一致

#### Scenario: chat 覆盖端点非法
- **WHEN** chat 的 `baseUrl` 不是 http/https 或不含 host
- **THEN** validation 在创建任何外部 client 前失败并指出 `llm.chat.baseUrl`

### Requirement: embedding 固定安全批处理合同
embedding SHALL 使用 `text-embedding-v4`、`dimensions=1024`、原始字符串输入、`check_embedding_ctx_length=false`，并把 client `chunk_size` 和每次远程调用的文本数限制为最多 10。输入超过单批上限时 MUST 分批调用并保持结果与原输入完全同序；空输入 MUST 直接返回空列表且不调用远程 client。

#### Scenario: 创建 embedding client
- **WHEN** provider 显式创建 embedding client
- **THEN** client 获得指定模型、1024 维、关闭 context length 检查和不大于 10 的 chunk size

#### Scenario: 十条以上文本分批
- **WHEN** 调用方按顺序提交 23 个原始字符串
- **THEN** provider 依次提交 10、10、3 条且不修改字符串，返回的 23 个向量保持相同顺序

#### Scenario: 空 embedding 输入
- **WHEN** 调用方提交空文本列表
- **THEN** provider 返回空向量列表且 embedding client 未被创建或调用

### Requirement: rerank 使用真实响应且不伪造分数
rerank SHALL 通过可注入异步 HTTP client 向可配置的 `qwen3-vl-rerank` endpoint 发送模型、query、documents、top_n 与 `return_documents=false`，并将响应的 index 和 relevance score 映射回原文档。timeout 默认 120 秒，瞬时 transport/timeout 失败最多重试 2 次；服务端错误或响应形状无效 MUST 返回安全错误，MUST NOT 生成 fallback 分数。

#### Scenario: 发送文本 rerank payload
- **WHEN** 调用方提交 query、三份文档和 top_n=2
- **THEN** HTTP payload 使用 qwen3-vl-rerank 的嵌套 input/parameters 结构，结果使用服务端返回的 index 与 relevance score

#### Scenario: timeout 后重试
- **WHEN** 前两次 rerank 调用发生 timeout 而第三次成功
- **THEN** provider 总共调用三次并返回第三次真实结果

#### Scenario: 重试耗尽
- **WHEN** 初始调用及 2 次 retry 均发生 transport 错误
- **THEN** provider 返回已脱敏错误且不返回任何合成排序或分数

### Requirement: readiness 使用最小异步真实路径并统一脱敏

provider readiness SHALL 分别对 chat、embedding、rerank 发起最小异步请求，并在成功时返回 `provider`、`model`、`baseUrl` 与非负 `latency`。chat 分支返回的 `baseUrl` MUST 是 chat 实际使用的生效端点，而不是顶层默认端点。任何失败异常在越过 provider 边界前 MUST 将该次调用实际使用的 API key 的全部出现替换为 `[redacted]`，且不得返回请求 header、完整配置或凭据。

#### Scenario: readiness 成功
- **WHEN** 注入 client 成功响应最小 chat、embedding 或 rerank 请求
- **THEN** readiness 返回对应 provider、模型、base URL 与非负 latency

#### Scenario: chat 使用独立端点时的 readiness
- **WHEN** chat 配置了独立 `baseUrl`，且注入的 chat client 成功响应最小请求
- **THEN** readiness 的 chat 结果返回 chat 的生效 base URL，而不是顶层 `llm.baseUrl`

#### Scenario: readiness 异常包含 API key
- **WHEN** 下游异常文本一次或多次包含当前 API key
- **THEN** provider 错误只保留 `[redacted]`，不包含原始 key

#### Scenario: chat 使用独立密钥时异常仍然脱敏
- **WHEN** chat 使用独立 `apiKey` 且下游异常文本包含该 chat 密钥
- **THEN** 错误信息中该密钥被替换为 `[redacted]`，顶层密钥同样不出现在错误里

### Requirement: 模块导入不产生网络副作用
导入模型配置、provider、rerank 或 readiness 模块 MUST NOT 创建外部 client、解析真实本机配置或连接网络。自动化测试 MUST 使用临时 JSON 与 fake transport；真实凭据 smoke SHALL 仅作为人工步骤记录，未执行时 MUST NOT 声称成功。

#### Scenario: 仅导入模型模块
- **WHEN** 独立进程在网络连接被禁止时导入全部模型 provider 模块
- **THEN** 导入成功且没有读取本机配置、创建 client 或连接网络

#### Scenario: 未运行真实凭据 smoke
- **WHEN** 自动化门禁只运行 fake transport 测试
- **THEN** 文档明确记录 smoke 未执行，不把自动化通过描述为真实百炼连通性通过

