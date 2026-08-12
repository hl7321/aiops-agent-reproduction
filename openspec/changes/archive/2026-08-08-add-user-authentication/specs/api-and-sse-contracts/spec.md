## MODIFIED Requirements

### Requirement: 共享错误目录保持稳定且可扩展
合同包 SHALL 提供稳定错误目录，至少包含 `AUTH_*`、`BUSINESS_*`、`VALIDATION_*` 和 `SYSTEM_*` 命名空间。每个错误 MUST 声明唯一 code、category、HTTP status 与安全默认消息；后续业务错误 SHALL 通过扩展目录增加，不得在 endpoint 内自造未登记 code。认证目录 MUST 包含统一登录失败的 `AUTH_INVALID_CREDENTIALS`、重复邮箱错误和受保护资源使用的 401 错误。

#### Scenario: 消费者读取错误定义
- **WHEN** 前端或合同测试按错误 code 查询目录
- **THEN** 获得稳定的 category、HTTP status 和安全默认消息

#### Scenario: 后续功能增加业务错误
- **WHEN** 后续提案需要新增业务失败语义
- **THEN** 先扩展共享错误目录和合同测试，再由 endpoint 使用该错误

#### Scenario: 登录凭据无效
- **WHEN** 邮箱不存在或已注册用户提供错误密码
- **THEN** 两种情况都使用同一个 `AUTH_INVALID_CREDENTIALS` 定义，不暴露账号是否存在

### Requirement: OpenAPI path 合同机器可读且先于 endpoint 扩展
共享合同 SHALL 以机器可读结构登记 OpenAPI path、method、operationId、成功响应语义和安全要求。目录 MUST 登记 `/health` 以及 `POST /auth/register`、`POST /auth/login`、`POST /auth/logout`、`GET /auth/me`；并 MUST 提供 `BearerAuth` HTTP bearer security scheme。后续提案 MUST 先扩展共享合同和合同测试，再增加对应 endpoint。

#### Scenario: 检查 foundation OpenAPI 合同
- **WHEN** 合同消费者读取共享 path 目录
- **THEN** 能定位 `/health` 的 GET method、稳定 operationId 和成功 envelope 数据类型

#### Scenario: 检查认证 OpenAPI 合同
- **WHEN** 合同消费者读取四个认证 path
- **THEN** 能获得稳定 method、operationId、Auth data 类型，并识别 logout 与 me 使用 `BearerAuth`

#### Scenario: 后续增加 endpoint
- **WHEN** 后续 change 计划增加 HTTP endpoint
- **THEN** 其任务和测试先修改共享 path 合同，再实现后端路由

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
后端无需导入 TypeScript，但其 Pydantic 模型、JSON 序列化、OpenAPI 路由、认证 DTO 和 SSE 形状 MUST 由合同测试证明与共享合同一致。仓库策略测试 MUST 阻止后端或前端新增临时 envelope、私有认证 payload、私有事件目录或重复事件判别联合。

#### Scenario: 比较后端与共享合同
- **WHEN** 运行后端和仓库合同测试
- **THEN** 成功、已知错误、验证错误、系统错误、request ID、认证 DTO/path/security、事件目录和工具生命周期的序列化形状均与共享合同一致

#### Scenario: 检测私有事件结构
- **WHEN** 前端或后端在允许的共享合同边界之外定义事件 type 目录、临时 envelope 或重复认证 payload
- **THEN** 仓库策略测试失败并指出违规文件
