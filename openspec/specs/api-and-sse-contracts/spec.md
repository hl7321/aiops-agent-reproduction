# API 与 SSE 合同规格

## Purpose

本能力为所有后续 HTTP 与 SSE 功能提供跨前后端一致、机器可读、可测试且可安全扩展的共享合同，避免各功能自行定义临时 payload。
## Requirements
### Requirement: HTTP 响应使用统一 envelope
所有成功 HTTP 响应 SHALL 使用 `{ok:true,data,meta:{requestId}}`，所有失败 HTTP 响应 SHALL 使用 `{ok:false,error:{code,category,httpStatus,message,details?},meta:{requestId}}`。`details` MAY 省略，其内容 MUST 可安全返回客户端。

#### Scenario: 返回成功响应
- **WHEN** endpoint 成功生成业务数据
- **THEN** 响应包含 `ok=true`、typed `data` 和与请求一致的 `meta.requestId`

#### Scenario: 返回目录中的业务错误
- **WHEN** endpoint 返回已登记的业务错误
- **THEN** 响应包含 `ok=false`，且 code、category、HTTP status 和安全默认消息与共享错误目录一致

#### Scenario: 请求验证失败
- **WHEN** 请求参数、路径或 body 不满足验证约束
- **THEN** 响应使用 `VALIDATION_*` 错误并在安全 details 中给出字段路径

#### Scenario: 未处理异常发生
- **WHEN** endpoint 抛出未处理异常
- **THEN** 响应使用安全的 `SYSTEM_*` 错误，不向客户端泄露内部异常文本或堆栈

### Requirement: 共享错误目录保持稳定且可扩展
合同包 SHALL 提供稳定错误目录，至少包含 `AUTH_*`、`BUSINESS_*`、`VALIDATION_*` 和 `SYSTEM_*` 命名空间。每个错误 MUST 声明唯一 code、category、HTTP status 与安全默认消息；后续业务错误 SHALL 通过扩展目录增加，不得在 endpoint 内自造未登记 code。认证目录 MUST 包含统一登录失败的 `AUTH_INVALID_CREDENTIALS`、重复邮箱错误和受保护资源使用的 401/403 错误；资源目录 MUST 包含不可枚举的 `BUSINESS_RESOURCE_NOT_FOUND` 404。

#### Scenario: 消费者读取错误定义
- **WHEN** 前端或合同测试按错误 code 查询目录
- **THEN** 获得稳定的 category、HTTP status 和安全默认消息

#### Scenario: 后续功能增加业务错误
- **WHEN** 后续提案需要新增业务失败语义
- **THEN** 先扩展共享错误目录和合同测试，再由 endpoint 使用该错误

#### Scenario: 登录凭据无效
- **WHEN** 邮箱不存在或已注册用户提供错误密码
- **THEN** 两种情况都使用同一个 `AUTH_INVALID_CREDENTIALS` 定义，不暴露账号是否存在

#### Scenario: 资源不可枚举错误
- **WHEN** 直接资源不存在或 owner scope 不匹配
- **THEN** 两种情况复用 `BUSINESS_RESOURCE_NOT_FOUND` 的相同 404 安全定义

### Requirement: 请求 ID 在 HTTP 边界透传或生成
后端 SHALL 接受合法非空 `X-Request-ID` 并透传到响应 header 与 envelope meta；请求未提供有效值时 SHALL 生成非空请求 ID。成功、验证失败、已知错误和未处理异常 MUST 使用同一个请求 ID。

#### Scenario: 客户端提供请求 ID
- **WHEN** 请求携带非空 `X-Request-ID`
- **THEN** 响应 header 与 envelope `meta.requestId` 均使用该值

#### Scenario: 客户端未提供请求 ID
- **WHEN** 请求不包含有效 `X-Request-ID`
- **THEN** 后端生成请求 ID，并同时写入响应 header 与 envelope meta

### Requirement: OpenAPI path 合同机器可读且先于 endpoint 扩展
共享合同 SHALL 以机器可读结构登记 OpenAPI path、method、operationId、成功响应语义和安全要求。目录 MUST 登记 `/health` 以及 `POST /auth/register`、`POST /auth/login`、`POST /auth/logout`、`GET /auth/me`；并 MUST 提供 `BearerAuth` HTTP bearer security scheme。所有当前及未来受保护 path MUST 引用 `BearerAuth`，并显式复用 `AUTH_REQUIRED` 401 与 `AUTH_FORBIDDEN` 403 响应合同。后续提案 MUST 先扩展共享合同和合同测试，再增加对应 endpoint。

#### Scenario: 检查 foundation OpenAPI 合同
- **WHEN** 合同消费者读取共享 path 目录
- **THEN** 能定位 `/health` 的 GET method、稳定 operationId 和成功 envelope 数据类型

#### Scenario: 检查认证 OpenAPI 合同
- **WHEN** 合同消费者读取四个认证 path
- **THEN** 能获得稳定 method、operationId、Auth data 类型，并识别 logout 与 me 使用 `BearerAuth` 和共享 401/403

#### Scenario: 后续增加 endpoint
- **WHEN** 后续 change 计划增加受保护 HTTP endpoint
- **THEN** 其共享 path 合同先声明 `BearerAuth`、`AUTH_REQUIRED` 与 `AUTH_FORBIDDEN`，再实现后端路由

### Requirement: SSE 使用共享判别联合
共享合同 SHALL 定义以 `type` 判别的 SSE 事件联合，事件公共字段 MUST 为 `id`、`type`、`channel`、`timestamp` 和单调递增的整数 `sequence`，其中 channel 仅允许 `chat` 或 `aiops`。事件目录 MUST 包含 `content.delta`、`reasoning.delta`、`tool.call`、`reference.source`、`task.status`、`report`、`complete` 和 `error`。

#### Scenario: 枚举全部 SSE 事件
- **WHEN** 合同测试遍历共享 SSE 事件目录
- **THEN** 八种 type 均存在且每种事件都携带公共字段与整数 sequence

#### Scenario: 表达工具调用生命周期
- **WHEN** SSE 发送 `tool.call` 事件
- **THEN** lifecycle 仅允许 `started`、`delta`、`completed` 或 `failed`，并携带稳定 toolCallId

#### Scenario: SSE 返回错误
- **WHEN** 流式处理需要发送 `error` 事件
- **THEN** 事件复用 HTTP failure envelope 中相同的 error 结构，不定义第二套错误 payload

### Requirement: 前端 transport 直接消费共享合同
前端 SHALL 提供 typed HTTP、SSE 与认证 transport 基础。HTTP client MUST 解包共享 envelope，并提供 bearer token 与 request ID 的注入扩展点；SSE client MUST 正确保留跨 chunk 的未完成 frame、解析完整 frame，并返回共享 SSE 联合；authClient MUST 直接消费共享 Auth DTO、请求和响应 data。前端 MUST NOT 复制私有 envelope、Auth payload 或事件联合。

#### Scenario: HTTP client 解包成功 envelope
- **WHEN** transport 收到 `ok=true` 的有效共享 envelope
- **THEN** 调用方获得 typed data，并可取得响应 request ID

#### Scenario: HTTP client 收到失败 envelope
- **WHEN** transport 收到 `ok=false` 的有效共享 envelope
- **THEN** 调用方收到携带共享 error 和 request ID 的 typed 错误

#### Scenario: SSE frame 跨网络 chunk
- **WHEN** 一个 SSE frame 被拆分到多个 chunk，或一个 chunk 包含多个 frame
- **THEN** parser 只在 frame 完整时产出共享事件，并保留剩余未完成文本供下一 chunk 使用

#### Scenario: authClient 调用认证 endpoint
- **WHEN** 前端注册、登录、登出或查询当前用户
- **THEN** 请求与响应直接使用共享 Auth 合同，并通过公共 ApiClient 注入 bearer token

### Requirement: 跨语言实现由合同测试约束
后端无需导入 TypeScript，但其 Pydantic 模型、JSON 序列化、OpenAPI 路由、认证 DTO 和 SSE 形状 MUST 由合同测试证明与共享合同一致。仓库策略测试 MUST 阻止后端或前端新增临时 envelope、私有认证 payload、私有事件目录、重复事件判别联合，或缺少 bearer/401/403 的受保护 path。

#### Scenario: 比较后端与共享合同
- **WHEN** 运行后端和仓库合同测试
- **THEN** 成功、已知错误、验证错误、系统错误、request ID、认证 DTO/path/security、受保护 path 错误响应、事件目录和工具生命周期的序列化形状均与共享合同一致

#### Scenario: 检测私有事件结构
- **WHEN** 前端或后端在允许的共享合同边界之外定义事件 type 目录、临时 envelope 或重复认证 payload
- **THEN** 仓库策略测试失败并指出违规文件

#### Scenario: 检测不完整受保护 path
- **WHEN** 机器可读目录中的 path 使用 bearer 但缺少共享 401 或 403
- **THEN** 合同测试失败并指出该 path

### Requirement: 共享合同登记后台任务管理边界
共享合同 SHALL 定义 BackgroundJob、BackgroundJobEvent、任务状态与取消/重试响应类型，并在机器可读 OpenAPI 目录登记 `GET /background-jobs`、`GET /background-jobs/{id}`、`POST /background-jobs/{id}:cancel` 和 `POST /background-jobs/{id}:retry`。四个 path MUST 使用 `BearerAuth` 并复用 `AUTH_REQUIRED`、`AUTH_FORBIDDEN` 与 `BUSINESS_RESOURCE_NOT_FOUND`。

#### Scenario: 合同消费者读取后台任务 path
- **WHEN** 前端或合同测试遍历共享 path 目录
- **THEN** 四个后台任务 path 具有稳定 method、operationId、成功数据类型、安全方案和错误列表

#### Scenario: 前后端序列化任务
- **WHEN** 后端返回任务详情或事件
- **THEN** Pydantic JSON 形状与 TypeScript 共享 DTO 一致且不包含 heartbeatAt 或 result

### Requirement: 共享合同登记知识文档上传与管理边界
共享合同 SHALL 定义 KnowledgeBase、KnowledgeDocument、ChunkingConfig、ChunkPreview DTO，以及 10 MiB、`.md/.pdf`、MIME、multipart 字段等上传 policy 常量。机器可读 OpenAPI 目录 MUST 登记知识库列表、文档列表/上传/详情/删除/预览六种操作；受保护 path MUST 使用 `BearerAuth` 并复用 401/403/404，上传额外登记 validation 与 `BUSINESS_CONFLICT` 409。

#### Scenario: 合同消费者读取上传 policy
- **WHEN** 前端或测试读取共享 policy
- **THEN** 获得精确最大字节数、扩展名/MIME 映射、multipart file/config/overwrite 字段和三种策略名

#### Scenario: 合同消费者读取知识 path
- **WHEN** 遍历机器可读 path 目录
- **THEN** 六种操作具有稳定 method、operationId、成功 DTO、安全方案与错误列表

### Requirement: 共享合同登记 durable 文档索引任务
共享合同 SHALL 定义 DocumentIndexTask DTO、`pending|running|succeeded|failed|cancelled` 状态联合、failureReason/retryOfTaskId 可选字段，以及创建任务、读取详情和 retry 三种受保护操作。机器可读 OpenAPI 目录 MUST 使用 bearer、统一 envelope/requestId，并复用 401/403/404/validation 错误；retry 返回新的任务 DTO。

#### Scenario: 合同消费者读取索引状态
- **WHEN** 前端或后端读取共享索引任务合同
- **THEN** 获得精确五种领域状态，且 queued 不是公开领域状态

#### Scenario: 合同消费者读取索引操作
- **WHEN** 遍历机器可读 path 目录
- **THEN** 创建、详情和 retry 具有稳定 method、operationId、成功 DTO、安全方案与错误列表

#### Scenario: API 返回 UI-ready 任务
- **WHEN** owner 创建、查询或重试索引任务
- **THEN** 成功 envelope 的 data 包含 task、document、KB、状态、failureReason、retryOfTaskId 和时间戳，且不包含 jobId

### Requirement: 共享合同登记 Knowledge Retrieval Tool
共享合同 SHALL 定义 KnowledgeRetrievalToolInput、KnowledgeRetrievalToolOutput 与 KnowledgeRetrievalCitation 类型。输入包含 query、可选 topK、knowledgeBaseIds 和 documentIds，但 MUST NOT 包含 ownerUserId 或 tenantId；citation 包含稳定 chunk/document/KB id、source/excerpt/metadata、vectorRank/vectorScore、bm25Rank/bm25Score、rrfScore、rerankRank/rerankScore 及兼容 score。此合同 MUST NOT 在机器可读 OpenAPI path 目录增加独立搜索 endpoint。

#### Scenario: 合同消费者创建 Tool 输入
- **WHEN** Agent 层使用共享 input 类型调用 knowledge_retrieval
- **THEN** 可表达 query、topK 和资源过滤，但不能通过合同传入 owner 或 tenant

#### Scenario: 合同消费者读取完整 citation
- **WHEN** Tool 返回双路或单路候选
- **THEN** citation 的阶段 rank/score 具有精确可空语义，且 score 与 rerankScore 均为必填数值

#### Scenario: OpenAPI 不暴露搜索产品 API
- **WHEN** 合同测试遍历机器可读 path 目录
- **THEN** 不存在为本 Tool 新增的独立 knowledge search HTTP path

### Requirement: 共享合同登记聊天会话与消息生命周期
共享合同 SHALL 定义 ChatSession、ChatMessage、ChatMessageMetadata、ChatReference、会话列表/详情、创建、追加、清空和删除的数据类型。message role MUST 限定为 `user|assistant|system|tool`，metadata MUST 允许保存 references 与 toolCallIds；删除成功数据 MUST 为 `{deleted:true,sessionId}`。

机器可读 OpenAPI 目录 MUST 登记 `POST /chat/sessions`、`GET /chat/sessions`、`GET /chat/sessions/{id}`、`POST /chat/sessions/{id}/messages`、`POST /chat/sessions/{id}/messages:clear` 和 `DELETE /chat/sessions/{id}`。所有路径 MUST 使用 `BearerAuth` 并复用 `AUTH_REQUIRED` 401 与 `AUTH_FORBIDDEN` 403；追加消息还 MUST 登记验证失败响应。

#### Scenario: 合同消费者读取聊天 DTO
- **WHEN** 前端或后端合同测试读取聊天类型
- **THEN** 获得稳定的会话、消息、role、metadata、reference、列表、详情、清空和删除数据形状

#### Scenario: 合同消费者读取聊天 path
- **WHEN** 合同测试遍历机器可读 OpenAPI path 目录
- **THEN** 六种聊天操作具有稳定 method、operationId、成功数据类型、BearerAuth 和共享 401/403 错误

#### Scenario: 追加消息验证失败
- **WHEN** 消息 role、content 或 metadata 不满足共享合同
- **THEN** 后端返回统一 validation error envelope，且序列化形状与共享合同一致

#### Scenario: 前后端禁止私有聊天 payload
- **WHEN** 仓库合同测试扫描聊天 transport、store 与后端响应模型
- **THEN** 它们直接消费共享聊天合同或由跨语言合同测试证明一致，不存在另一套临时会话或消息结构

### Requirement: 共享合同登记 Agent 流式聊天与工具审计
共享合同 SHALL 定义 ChatStreamMessageRequest、AgentToolCallAudit、审计状态与审计列表 data，并在机器可读 OpenAPI 目录登记 `POST /chat/sessions/{sessionId}/messages:stream` 和 `GET /chat/sessions/{sessionId}/tool-call-audits`。两个 path MUST 使用 `BearerAuth` 并复用 401/403；stream 还 MUST 登记 validation 与共享 SSE response。

#### Scenario: 合同消费者读取 stream path
- **WHEN** 合同测试读取流式消息 operation
- **THEN** 获得稳定 method、operationId、user content/metadata 请求、共享 SSE response、BearerAuth 和 401/403/validation 错误

#### Scenario: 合同消费者读取审计 DTO 与 path
- **WHEN** 合同测试读取会话工具审计 operation
- **THEN** 获得稳定 audit 字段、状态、父对象二选一语义、列表 data、BearerAuth 和 401/403

#### Scenario: 前端消费流式事件
- **WHEN** chat transport 收到跨网络 chunk 的流式消息事件
- **THEN** 它通过公共 SSE parser 与共享 event union 保留 id/sequence 并完成类型收窄，不复制私有事件联合

### Requirement: 共享合同登记 Chat Prompt、Skill 与 configuration
共享合同 SHALL 定义 ChatPrompt、ChatSkill、ChatConfiguration、Prompt create/update、configuration update、删除结果与 Skill multipart policy。机器可读 OpenAPI 目录 MUST 登记 `GET/PUT /chat/configuration`、`POST /chat/prompts`、`PUT/DELETE /chat/prompts/{id}`、`POST /chat/skills`、`DELETE /chat/skills/{id}` 七个 operation；全部使用 `BearerAuth` 并复用 401/403/404，创建或上传按需登记 validation 与 `BUSINESS_CONFLICT` 409。

#### Scenario: 合同消费者读取 configuration DTO
- **WHEN** 前端或后端读取共享配置合同
- **THEN** 获得 prompts、skills、nullable selectedPromptId 与 selectedSkillIds 的稳定类型，以及 Prompt/Skill 的可编辑字段

#### Scenario: 合同消费者读取 Skill 上传 policy
- **WHEN** 客户端构建 Skill multipart 请求
- **THEN** 获得严格 filename `SKILL.md`、file 字段、256 KiB 限制、name/description 边界和规范化约束

#### Scenario: 合同消费者读取七个 operation
- **WHEN** 合同测试遍历机器可读 path 目录
- **THEN** 七个 operation 具有稳定 method、operationId、成功 DTO、BearerAuth 与共享错误列表

#### Scenario: 前端不复制配置 payload
- **WHEN** configuration client/store 发送选择或资产请求
- **THEN** 它直接消费共享 DTO 与 multipart policy，不定义另一套私有 Prompt/Skill payload

### Requirement: 共享合同定义会话记忆 DTO 与操作
共享 contracts SHALL 定义 `every_30_turns|context_70_percent|manual` 记忆模式、Chat session 的记忆字段、更新模式请求，以及 `PUT /chat/sessions/{id}/memory` 和 `POST /chat/sessions/{id}/memory:compact` 两条 bearer-protected OpenAPI operation。后端 Pydantic 序列化、前端 TypeScript 类型和机器可读 manifest MUST 保持一致。

#### Scenario: 合同读取会话记忆
- **WHEN** contracts 测试构造带完整记忆字段的 ChatSession
- **THEN** TypeScript、Pydantic 与 manifest 对字段名称、nullable 语义和模式目录一致

#### Scenario: 两条记忆操作受保护
- **WHEN** 检查机器可读 OpenAPI operation
- **THEN** 两条 path 使用 bearer 并声明共享 401、403、validation 与安全系统错误

### Requirement: 上下文上限使用稳定 HTTP 与 SSE 错误
稳定错误目录 SHALL 增加 `CHAT_CONTEXT_LIMIT_REACHED`，category 为 `business`、HTTP status 为 409，并提供不包含 prompt、消息、摘要或模型凭据的安全默认消息。HTTP failure envelope 与 SSE `error` MUST 复用相同 `ApiErrorModel` 字段，不能复制私有错误 payload。

#### Scenario: HTTP 上下文拒绝
- **WHEN** 流式 endpoint 在响应开始前拒绝达到 95% 的候选消息
- **THEN** failure envelope 返回 code、business category、409、安全 message 和 requestId

#### Scenario: SSE 上下文错误
- **WHEN** 已开始的流必须用上下文上限错误终止
- **THEN** `error` event 的 error 对象与目录中的 code、category、httpStatus 和默认消息一致

### Requirement: 模型 capability 缺失使用稳定配置错误
稳定错误目录 SHALL 增加 `SYSTEM_MODEL_CAPABILITY_MISSING`，用于当前 chat model 缺失有效 `contextWindowTokens` 的情况。错误 MUST 在创建模型 client 前产生并保持凭据脱敏，HTTP 与 SSE MUST 复用同一结构。

#### Scenario: 会话预算无法取得窗口
- **WHEN** 当前模型没有 capability profile
- **THEN** API 返回 `SYSTEM_MODEL_CAPABILITY_MISSING` 的安全系统错误，不使用猜测窗口继续执行

### Requirement: 共享合同登记 MCP 连接与检查边界
共享 contracts SHALL 定义 McpConnection、McpDiscoveredTool、McpConnectionCheckResult、create/update/delete 数据、`sse|streamable_http` transport 与 `connected|failed` check 状态。机器可读 OpenAPI 目录 MUST 登记 `GET/POST /mcp/connections`、`PUT/DELETE /mcp/connections/{id}` 与 `POST /mcp/connections/{id}:check` 五个 operation；全部使用 BearerAuth 并复用 401/403，create/update 声明 validation/conflict，check 声明安全 MCP 系统错误。TypeScript、Pydantic、manifest 和前端 transport MUST 对字段、nullable 语义与错误目录保持一致。

#### Scenario: 合同消费者读取 MCP DTO
- **WHEN** 前端或后端合同测试构造带最近检查和发现 tools 的连接
- **THEN** transport、URL、范围字段、nullable 状态与 tool 快照形状在跨语言实现中一致

#### Scenario: 五个 MCP operations 受保护
- **WHEN** 合同测试遍历 MCP path 目录
- **THEN** 每个 operation 具有稳定 method、operationId、成功 DTO、BearerAuth 和对应共享错误

#### Scenario: MCP 失败使用稳定错误
- **WHEN** Chat 装配因连接失败或 tool 同名冲突而终止
- **THEN** HTTP/SSE 使用共享目录中的安全 code、category、httpStatus 与 message，不自造私有 MCP error payload
