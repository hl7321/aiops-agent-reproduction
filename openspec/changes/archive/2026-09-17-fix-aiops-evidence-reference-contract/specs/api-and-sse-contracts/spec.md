## MODIFIED Requirements

### Requirement: SSE 使用共享判别联合
共享合同 SHALL 定义以 `type` 判别的 SSE 事件联合，事件公共字段 MUST 为 `id`、`type`、`channel`、`timestamp` 和单调递增的整数 `sequence`，其中 channel 仅允许 `chat` 或 `aiops`。事件目录 MUST 包含 `content.delta`、`reasoning.delta`、`tool.call`、`reference.source`、`task.status`、`report`、`complete` 和 `error`。`task.status` 的 lifecycle MUST 仅允许 `queued|running|succeeded|failed|cancelled`，并支持 nullable 中文 message 与 0..100 nullable progress；不得为计划、步骤或重规划增加新的 SSE type。`reference.source` 在 `aiops` 频道下承载诊断证据引用，其证据种类 MUST 覆盖 `DiagnosticEvidenceKind` 定义的全部种类；该种类的 TypeScript 类型与运行时校验 MUST 引用同一份种类清单，不得维护第二份手写列表。

#### Scenario: 枚举全部 SSE 事件
- **WHEN** 合同测试遍历共享 SSE 事件目录
- **THEN** 八种 type 均存在且每种事件都携带公共字段与整数 sequence

#### Scenario: 表达工具调用生命周期
- **WHEN** SSE 发送 `tool.call` 事件
- **THEN** lifecycle 仅允许 `started`、`delta`、`completed` 或 `failed`，并携带稳定 toolCallId

#### Scenario: SSE 返回错误
- **WHEN** 流式处理需要发送 `error` 事件
- **THEN** 事件复用 HTTP failure envelope 中相同的 error 结构，不定义第二套错误 payload

#### Scenario: 表达 durable task 进度
- **WHEN** 后台诊断排队、执行、成功、失败或取消
- **THEN** task.status 使用对应 lifecycle、可访问 message 和有界 progress，不创建 plan/step/replan 事件

#### Scenario: 表达诊断证据引用
- **WHEN** SSE 在 `aiops` 频道发送 `reference.source`，其证据种类取自诊断证据种类清单中的任意一种
- **THEN** guard 判定该事件合法；当证据种类不在清单内时，guard MUST 拒绝该事件

### Requirement: 跨语言实现由合同测试约束
后端无需导入 TypeScript，但其 Pydantic 模型、JSON 序列化、OpenAPI 路由、认证 DTO 和 SSE 形状 MUST 由合同测试证明与共享合同一致。仓库策略测试 MUST 阻止后端或前端新增临时 envelope、私有认证 payload、私有事件目录、重复事件判别联合，或缺少 bearer/401/403 的受保护 path。合同测试 MUST 遍历诊断证据种类的全部取值，证明 `reference.source` 的 aiops 形状在 TypeScript 与后端两侧同时成立。

#### Scenario: 比较后端与共享合同
- **WHEN** 运行后端和仓库合同测试
- **THEN** 成功、已知错误、验证错误、系统错误、request ID、认证 DTO/path/security、受保护 path 错误响应、事件目录和工具生命周期的序列化形状均与共享合同一致

#### Scenario: 检测私有事件结构
- **WHEN** 前端或后端在允许的共享合同边界之外定义事件 type 目录、临时 envelope 或重复认证 payload
- **THEN** 仓库策略测试失败并指出违规文件

#### Scenario: 检测不完整受保护 path
- **WHEN** 机器可读目录中的 path 使用 bearer 但缺少共享 401 或 403
- **THEN** 合同测试失败并指出该 path

#### Scenario: 遍历诊断证据种类
- **WHEN** 合同测试为诊断证据种类的每一个取值构造 `reference.source` 事件
- **THEN** 每个取值都通过共享合同校验，且后端生成的证据引用形状与共享合同一致
