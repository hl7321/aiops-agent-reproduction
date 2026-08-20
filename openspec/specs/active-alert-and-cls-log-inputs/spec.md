# 活跃告警与 CLS 日志输入规格

## Purpose

本能力为后续 AIOps 提供 deployment-global 的真实活跃告警输入，并提供与应用运行时隔离、只有人工显式执行才会产生外部写入的腾讯 CLS 结构化日志工具。

## Requirements

### Requirement: 本地 JSON 定义 deployment-global 告警来源
合并后的 `prometheusAlerts.sources` SHALL 支持多个具名 source，每个 source 的 type MUST 为 `prometheus-v1|alertmanager-v2`，并包含有效 HTTP(S) baseUrl、正数 timeoutSeconds 和可选 Basic Auth。username/password 只能来自被 Git 忽略的本机 JSON，应用不得从 OS 环境变量补充。source 是 deployment-global 项目配置，MUST NOT 被建模为 user-owned Repository 数据。

#### Scenario: 两种来源并存
- **WHEN** 本机 JSON 配置一个 Prometheus v1 source 和一个 Alertmanager v2 source
- **THEN** typed 配置保留两个 source 的名称、类型、地址、timeout 与各自可选认证信息

#### Scenario: 非法来源配置
- **WHEN** source 类型未知、名称重复、baseUrl 缺少 host、timeout 非正数或 Basic Auth 只填写一侧
- **THEN** 系统在创建任何 HTTP client 或发起网络请求前返回不包含凭据的明确配置错误

### Requirement: Provider 标准化真实活跃告警
系统 SHALL 通过异步 HTTP 请求读取 Prometheus `GET /api/v1/alerts` 或 Alertmanager `GET /api/v2/alerts` 的真实响应，并把每条告警标准化为 alertName、nullable service、nullable severity、`pending|firing|suppressed|unprocessed` status、startsAt、labels、annotations、source 与 rawContext。Prometheus `activeAt` MUST 映射为 startsAt；Alertmanager `active` status MUST 映射为 `firing`，其原始 provider 记录仍保存在 rawContext。系统 MUST NOT 构造默认告警或伪造缺失来源数据。

#### Scenario: Prometheus firing payload
- **WHEN** Prometheus 返回 status=success 且包含 state=firing 的 active alert
- **THEN** provider 返回 source 类型为 prometheus-v1、status=firing、startsAt 来自 activeAt 且 labels/annotations/rawContext 可追溯的标准告警

#### Scenario: Alertmanager suppressed payload
- **WHEN** Alertmanager 返回 status.state=suppressed 的告警
- **THEN** provider 保留 suppressed、startsAt、source、labels、annotations 与完整单条 rawContext，不把它伪装成 firing

#### Scenario: Provider payload 无效
- **WHEN** 上游返回非 2xx、非 JSON 或不符合对应 API 形状的 payload
- **THEN** 该 source 以安全失败结束，错误不得包含 Basic Auth password 或完整敏感响应正文

### Requirement: Aggregator 允许部分来源失败但禁止虚构结果
Aggregator SHALL 并发读取全部配置 source，并以 source name、startsAt、alertName 的稳定顺序返回成功来源的真实标准告警。任一 source 失败时 MUST 保留其他 source 的结果；零 source 或全部 source 失败时 MUST 返回稳定的 `SYSTEM_ALERT_SOURCES_UNAVAILABLE` 503。成功响应 SHALL 只包含 items，不得增加 provider 状态集合或用空告警掩盖全失败。

#### Scenario: 单源失败
- **WHEN** 两个 source 中一个请求失败且另一个返回两条真实告警
- **THEN** API 成功返回该两条标准告警，且响应中没有 providerStatuses 等状态集合

#### Scenario: 成功来源没有告警
- **WHEN** 至少一个 source 请求成功但其 items 为空，其他 source 可成功或失败
- **THEN** API 成功返回空 items，不构造默认告警

#### Scenario: 全部来源失败
- **WHEN** 所有已配置 source 均请求失败或没有配置 source
- **THEN** API 返回 `SYSTEM_ALERT_SOURCES_UNAVAILABLE` 503 failure envelope，不返回成功空列表

### Requirement: 活跃告警通过认证 API 暴露
系统 SHALL 提供 bearer-protected `GET /aiops/alerts/active`，成功时使用共享 envelope 返回 `{items: ActiveAlert[]}`。访问者必须是已认证 CurrentUser，但告警 source 与读取结果仍是 deployment-global，不按用户复制配置或伪造 owner 字段。未认证访问 MUST 返回共享 401，认证用户访问不得因没有 user-owned source 返回 403。

#### Scenario: 已认证读取活跃告警
- **WHEN** 任一已认证用户请求 endpoint 且 aggregator 至少有一个成功 source
- **THEN** API 返回统一 success envelope、requestId 与标准化 items

#### Scenario: 未认证读取活跃告警
- **WHEN** 请求不带有效 bearer token
- **THEN** API 返回共享 `AUTH_REQUIRED` 401 envelope，且不请求任何告警 source

### Requirement: CLS 日志工具只在人工显式执行时写入
仓库 SHALL 提供独立 Python CLI，从显式 project/user JSON 深合并结果读取 `clsLogUpload`。配置 MUST 包含 HTTPS endpoint、region、topicId、可选 logsetId、secretId 与 secretKey；logsetId 只供人工关联，MUST NOT 作为 SDK 上传参数。CLI MUST 使用 endpoint 创建官方 SDK LogClient，并只通过 `put_log_raw(topicId, groups)` 上传。import、测试、FastAPI 创建、lifespan 和普通应用启动 MUST NOT 创建 SDK client 或上传日志。

#### Scenario: import 与应用启动
- **WHEN** 测试 import CLI 模块并创建或启动 FastAPI app
- **THEN** SDK client 未创建、put_log_raw 未调用且没有网络或 CLS 写入

#### Scenario: 显式上传
- **WHEN** 用户人工执行 CLI，count 与配置合法且已确认自己的 endpoint/topic 目标
- **THEN** client 由配置 endpoint/凭据创建，并恰好调用一次 `put_log_raw(topicId, groups)`

#### Scenario: logsetId 不参与路由
- **WHEN** clsLogUpload 配置包含 logsetId
- **THEN** logsetId 只保留在安全配置/人工说明中，SDK client 与 put_log_raw 参数不使用它

### Requirement: CLS 结构化日志有界且不泄密
CLI SHALL 支持 count 参数且限制为 1..100；每条生成日志 MUST 包含 region、service、severity、level、traceId、timestamp 与有界 message，不得包含 secretId、secretKey、password、token 或用户输入的任意秘密。标准输出和所有安全错误 MUST 替换当前 secretId/secretKey 为 `[redacted]`，不得打印凭据；普通自动化测试只使用 fake SDK 边界。

#### Scenario: count 上限
- **WHEN** count 为 0、负数或大于 100
- **THEN** CLI 在创建 SDK client 前拒绝执行且不上传任何日志

#### Scenario: 生成安全 payload
- **WHEN** CLI 以 count=3 生成待上传日志组
- **THEN** payload 恰好包含三条有界结构化日志，每条带 region 且不含任何配置凭据

#### Scenario: SDK 异常包含凭据
- **WHEN** fake SDK 抛出的异常文本意外包含当前 secretId 或 secretKey
- **THEN** CLI 输出/抛出的安全错误只显示 `[redacted]`，不泄露原值

#### Scenario: 未确认真实写入
- **WHEN** 运行自动化门禁、开发服务器或普通 smoke 且用户未针对 CLS 目标确认
- **THEN** 不执行真实 CLS 上传，也不声称真实写入通过

### Requirement: 本阶段只提供 AIOps 输入
活跃告警 API 与 CLS 日志工具 SHALL 只提供后续诊断可消费的输入，不生成根因、诊断结论、报告、处置建议或自动 remediation。

#### Scenario: 读取告警完成
- **WHEN** 客户端成功读取一组活跃告警
- **THEN** 响应只包含标准化告警 items，不包含模型生成的诊断、报告或处置动作
