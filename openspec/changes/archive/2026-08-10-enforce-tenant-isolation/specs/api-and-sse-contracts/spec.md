## MODIFIED Requirements

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
