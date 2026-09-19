## MODIFIED Requirements

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
