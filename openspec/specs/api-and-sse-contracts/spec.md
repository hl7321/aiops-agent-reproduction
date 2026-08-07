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
合同包 SHALL 提供稳定错误目录，至少包含 `AUTH_*`、`BUSINESS_*`、`VALIDATION_*` 和 `SYSTEM_*` 命名空间。每个错误 MUST 声明唯一 code、category、HTTP status 与安全默认消息；后续业务错误 SHALL 通过扩展目录增加，不得在 endpoint 内自造未登记 code。

#### Scenario: 消费者读取错误定义
- **WHEN** 前端或合同测试按错误 code 查询目录
- **THEN** 获得稳定的 category、HTTP status 和安全默认消息

#### Scenario: 后续功能增加业务错误
- **WHEN** 后续提案需要新增业务失败语义
- **THEN** 先扩展共享错误目录和合同测试，再由 endpoint 使用该错误

### Requirement: 请求 ID 在 HTTP 边界透传或生成
后端 SHALL 接受合法非空 `X-Request-ID` 并透传到响应 header 与 envelope meta；请求未提供有效值时 SHALL 生成非空请求 ID。成功、验证失败、已知错误和未处理异常 MUST 使用同一个请求 ID。

#### Scenario: 客户端提供请求 ID
- **WHEN** 请求携带非空 `X-Request-ID`
- **THEN** 响应 header 与 envelope `meta.requestId` 均使用该值

#### Scenario: 客户端未提供请求 ID
- **WHEN** 请求不包含有效 `X-Request-ID`
- **THEN** 后端生成请求 ID，并同时写入响应 header 与 envelope meta

### Requirement: OpenAPI path 合同机器可读且先于 endpoint 扩展
共享合同 SHALL 以机器可读结构登记 OpenAPI path、method、operationId 和成功响应语义；本变更只登记 foundation `/health`。后续提案 MUST 先扩展共享合同和合同测试，再增加对应 endpoint。

#### Scenario: 检查 foundation OpenAPI 合同
- **WHEN** 合同消费者读取共享 path 目录
- **THEN** 能定位 `/health` 的 GET method、稳定 operationId 和成功 envelope 数据类型

#### Scenario: 后续增加 endpoint
- **WHEN** 后续 change 计划增加 HTTP endpoint
- **THEN** 其任务和测试先修改共享 path 合同，再实现后端路由

### Requirement: SSE 使用共享判别联合
共享合同 SHALL 定义以 `type` 判别的 SSE 事件联合，事件公共字段 MUST 为 `id`、`type`、`channel` 和 `timestamp`，其中 channel 仅允许 `chat` 或 `aiops`。事件目录 MUST 包含 `content.delta`、`reasoning.delta`、`tool.call`、`reference.source`、`task.status`、`report`、`complete` 和 `error`。

#### Scenario: 枚举全部 SSE 事件
- **WHEN** 合同测试遍历共享 SSE 事件目录
- **THEN** 八种 type 均存在且每种事件都携带公共字段

#### Scenario: 表达工具调用生命周期
- **WHEN** SSE 发送 `tool.call` 事件
- **THEN** lifecycle 仅允许 `started`、`delta`、`completed` 或 `failed`，并携带稳定 toolCallId

#### Scenario: SSE 返回错误
- **WHEN** 流式处理需要发送 `error` 事件
- **THEN** 事件复用 HTTP failure envelope 中相同的 error 结构，不定义第二套错误 payload

### Requirement: 前端 transport 直接消费共享合同
前端 SHALL 提供 typed HTTP 与 SSE transport 基础。HTTP client MUST 解包共享 envelope，并提供 bearer token 与 request ID 的注入扩展点；SSE client MUST 正确保留跨 chunk 的未完成 frame、解析完整 frame，并返回共享 SSE 联合。前端 MUST NOT 复制私有事件联合。

#### Scenario: HTTP client 解包成功 envelope
- **WHEN** transport 收到 `ok=true` 的有效共享 envelope
- **THEN** 调用方获得 typed data，并可取得响应 request ID

#### Scenario: HTTP client 收到失败 envelope
- **WHEN** transport 收到 `ok=false` 的有效共享 envelope
- **THEN** 调用方收到携带共享 error 和 request ID 的 typed 错误

#### Scenario: SSE frame 跨网络 chunk
- **WHEN** 一个 SSE frame 被拆分到多个 chunk，或一个 chunk 包含多个 frame
- **THEN** parser 只在 frame 完整时产出共享事件，并保留剩余未完成文本供下一 chunk 使用

### Requirement: 跨语言实现由合同测试约束
后端无需导入 TypeScript，但其 Pydantic 模型、JSON 序列化、OpenAPI 路由和 SSE 形状 MUST 由合同测试证明与共享合同一致。仓库策略测试 MUST 阻止后端或前端新增临时 envelope、私有事件目录或重复事件判别联合。

#### Scenario: 比较后端与共享合同
- **WHEN** 运行后端和仓库合同测试
- **THEN** 成功、已知错误、验证错误、系统错误、request ID、事件目录和工具生命周期的序列化形状均与共享合同一致

#### Scenario: 检测私有事件结构
- **WHEN** 前端或后端在允许的共享合同边界之外定义事件 type 目录或临时 envelope
- **THEN** 仓库策略测试失败并指出违规文件
