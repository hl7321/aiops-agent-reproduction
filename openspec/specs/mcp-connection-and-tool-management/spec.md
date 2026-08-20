# MCP 连接与工具管理规格

## Purpose

本能力为每个认证用户提供服务端持久化的 MCP Server 连接管理、真实工具发现与安全调用边界，使 Chat 和后续 AIOps 共用同一 owner-scoped 连接事实来源。

## Requirements

### Requirement: MCP 连接按 owner 持久化
系统 SHALL 为每条 MCP 连接持久化 owner、name、`transport`、url、enabled、timeoutSeconds、retries、nullable lastCheck、nullable lastError、discoveredTools、createdAt 与 updatedAt。`transport` MUST 只允许 `sse|streamable_http`，timeoutSeconds MUST 为 1..300，retries MUST 为 0..5。所有 list/create/update/delete/check 必须在同一 Repository 语句中限定当前 owner，不得把 ORM model 传入领域服务。

#### Scenario: 两个用户管理同名连接
- **WHEN** 用户 A 与 B 分别创建同名连接
- **THEN** 两条连接可独立保存，且任一用户都不能读取、修改、删除或检查另一用户的连接

#### Scenario: 超出范围的连接参数
- **WHEN** 创建或更新使用非法 transport、timeoutSeconds 或 retries
- **THEN** 后端返回共享 validation error，且不保存部分更新

### Requirement: MCP URL 有权威安全校验
后端 SHALL 只接受 `http` 或 `https` URL，URL MUST 具有 host 且 MUST NOT 包含 userinfo。当前版本 MUST NOT 接收或持久化自定义 headers。合法 URL 的 path 和 query SHALL 完整持久化并返回，因此用户文档和页面 MUST 明确禁止在 URL query 中放置 token、secret、password 或其他凭据。结构化日志和安全错误 MUST NOT 输出 URL query。

#### Scenario: URL 含 userinfo
- **WHEN** 用户提交 `https://user:password@example.test/mcp`
- **THEN** 后端拒绝请求并且错误不回显 userinfo

#### Scenario: URL 带普通 query
- **WHEN** 用户提交具有 host、path 和非凭据 query 的合法 URL
- **THEN** 服务端原样持久化并在 owner-scoped DTO 中返回完整 URL，同时 UI 显示凭据禁止提示

### Requirement: MCP API 管理连接并真实检查
系统 SHALL 提供 `GET/POST /mcp/connections`、`PUT/DELETE /mcp/connections/{id}` 与 `POST /mcp/connections/{id}:check`。check MUST 使用该连接的 transport、完整 URL、timeout 和 retry 真实连接 MCP Server 并列出实际工具；成功时更新 lastCheck、清空 lastError 并保存 discoveredTools，失败时更新 lastCheck、安全 lastError 并清空 discoveredTools。check 响应 SHALL 明确返回 `connected|failed`、真实工具列表与 nullable 安全错误，不得用假工具补齐。

#### Scenario: 真实检查成功
- **WHEN** owner 检查一个可访问且返回两个工具的 MCP Server
- **THEN** 响应 status 为 connected，tools 来自当次真实 discovery，持久化快照与响应一致

#### Scenario: 真实检查失败
- **WHEN** 连接超时或 Server 返回错误
- **THEN** 系统在有界尝试后返回 failed 和脱敏错误，并不返回旧工具或假结果

#### Scenario: 工具目录越界
- **WHEN** MCP Server 返回超过 500 个工具、空白或超长工具名、超长 description
- **THEN** 系统把该次 check 记为安全失败并清空工具快照，不持久化越界目录且不返回内部验证异常

### Requirement: 工具发现与聚合使用有界真实连接
运行时 SHALL 按当前 owner 只读取 enabled 持久连接，并为当前请求真实发现 LangChain-compatible MCP tools。disabled 连接 MUST 在创建外部 client 前被排除。每次连接尝试总数 MUST 等于 `retries + 1`，每次尝试受 timeoutSeconds 约束；任一必需连接失败 MUST 使本次装配显式失败，不得静默跳过。不同 MCP Server 或 MCP 与内建工具存在同名 tool 时 MUST 返回稳定冲突错误，不得随机选择、覆盖或重复调用。

#### Scenario: 禁用连接不连网
- **WHEN** owner 具有一条 enabled 和一条 disabled 连接并开始 Agent 请求
- **THEN** 只对 enabled 连接创建 client 与发现工具，disabled 连接的 transport 不被调用

#### Scenario: 有界重试后成功
- **WHEN** retries 为 2 且 Server 前两次连接失败、第三次成功
- **THEN** 系统恰好尝试三次并且只返回一份发现工具集

#### Scenario: 两个 Server 发现同名工具
- **WHEN** 两个 enabled Server 都发现 `query_logs`
- **THEN** 整个聚合返回工具名冲突错误，Agent 不使用其中任一个

### Requirement: 默认 CLS 配置只作为真实回退来源
仅当当前 owner 没有 enabled 持久 MCP 连接且本地 JSON 深合并结果包含非空 `clsMcpServer.baseUrl` 时，运行时 SHALL 将它作为一个临时真实连接来源。该回退 MUST 受同样 URL、timeout、retry、真实 discovery 和同名冲突约束，MUST NOT 生成持久化假 profile、静态 tool 目录或假调用结果。无 enabled 连接且 baseUrl 为空时 SHALL 返回空 MCP 工具集且不连网。

#### Scenario: 用户连接优先
- **WHEN** owner 已有 enabled 持久连接且配置也有 CLS baseUrl
- **THEN** 运行时只聚合 owner 连接，不连接 CLS 回退

#### Scenario: 空配置不伪造连接
- **WHEN** owner 没有 enabled 连接且 CLS baseUrl 为空
- **THEN** MCP 工具集为空，系统不创建 client、不返回假 profile 或假 tools

### Requirement: MCP 桌面工作区以服务器为事实来源
前端 SHALL 提供 typed MCP client、可清理 Pinia store 和 `/mcp` 桌面管理页，支持列表、新建、编辑、启停、删除、SSE/Streamable HTTP 选择、检查状态与真实工具目录展示。写操作成功后 store MUST 以服务端 DTO 对账；MCP 连接或工具数据 MUST NOT 写入 localStorage 或用静态数组伪造。所有 loading、empty、error、enabled、check 状态 MUST 有中文文字/ARIA，不能只靠颜色。

#### Scenario: 检查并展示真实工具
- **WHEN** 用户在 `/mcp` 对连接执行成功检查
- **THEN** 页面用 check 响应与刷新后服务端 DTO 展示实际 tool name/description，不插入演示工具

#### Scenario: 认证失效清理
- **WHEN** MCP API 返回 401 或用户 logout
- **THEN** store 清理内存中连接、表单与工具快照，忽略该认证世代仍在途的旧响应，且不请求删除服务端连接

### Requirement: 自动化替身不得成为产品运行时实现
产品运行时 MUST 通过真实 MCP 协议 client 发现和调用工具，MUST NOT 包含 mock profile、静态假工具列表、假 transport 或 fallback result。自动化测试 MAY 通过显式注入可控 transport/client 替身，但测试通过 MUST NOT 被声称为真实 MCP 连通。真实官方 CLS MCP smoke 只在主机服务与所需凭据可用时执行，不可用时 MUST 明确记录未执行。

#### Scenario: 单测使用 fake transport
- **WHEN** 自动化测试注入 fake transport 并验证 discovery/invocation
- **THEN** 测试只证明边界逻辑，文档不声称已连通官方 CLS MCP
