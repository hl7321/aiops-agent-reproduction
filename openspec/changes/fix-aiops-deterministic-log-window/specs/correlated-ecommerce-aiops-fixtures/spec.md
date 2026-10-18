# Spec Delta

## MODIFIED Requirements

### Requirement: CLS 脚本扩展既有入口而不复制实现
仓库 SHALL 继续只提供一个 `generate_and_upload_cls_logs.py`。它 MUST 保持既有量化 profile/count 调用兼容，并为固定十套 `java-ecommerce` incident 分别生成稳定、互相隔离的 context flow 和多条有序日志。十套 incident 的日志时间 MUST 依次落在生成时刻之前的 9 分钟内（最早为 T−9 分钟、最晚为 T），每套内部的四段日志保持原有秒级顺序，使紧接着发布的告警自然落在日志之后。每条日志 MUST 保持完整关联字段；脚本只有在用户显式 CLI 调用并确认自己的 CLS 目标时才可创建 SDK client 和上传。当前 PutLogs 上传链路不保证产出 `PkgId`/`PkgLogId`，因此本 profile MUST NOT 声称 DescribeLogContext 可用；是否恢复该工具由独立变更决定。

#### Scenario: Java CLS 显式上传
- **WHEN** 用户选择 java-ecommerce profile、确认目标且本地 CLS 配置有效
- **THEN** 脚本为十套 incident 上传相互隔离的多行上下文，并只输出安全数量与 request id

#### Scenario: 日志时间位于告警之前
- **WHEN** 脚本在时刻 T 生成十套 Java fixture，且用户在随后发布告警
- **THEN** 最早一套日志时间为 T−9 分钟、最晚一套为 T，默认 `[告警时刻 − 15 分钟, 告警时刻]` 窗口能够覆盖全部十套日志

#### Scenario: 同一 incident 上下文稳定
- **WHEN** SearchLog 命中任一 Java incident 的错误日志
- **THEN** 结果含可用 Time 与同 incident 的有序上下文，不混入其他 incident；不得声明 PkgId/PkgLogId 一定非空

#### Scenario: 量化 profile 兼容
- **WHEN** 用户沿用既有 count 调用或显式选择量化 profile
- **THEN** 脚本仍接受 1..100 的 count 并生成原有有界日志，不改变既有 CLS 路由与脱敏语义

### Requirement: Alertmanager 发布必须显式选择并确认目标
仓库 SHALL 提供 `publish_java_ecommerce_alerts.py`，仅通过显式 CLI 向用户给出的 HTTP(S) Alertmanager base URL 发布十条 v2 alerts。URL MUST 有 host、拒绝 userinfo；脚本 MUST 要求显式确认目标，设置有界 timeout，并在非 2xx、网络或响应错误时非零退出且不得声称成功。脚本 SHALL 支持 `--starts-at <ISO 8601>`（必须带时区，未提供时使用当前时间）、`--active-days <正数>`（未提供时保持 2 小时）与 `--ensure`（已有 10 条活跃告警时跳过发布）。`endsAt` MUST 为 `startsAt + 生效时长`。

#### Scenario: 发布十条真实告警
- **WHEN** 用户显式指定并确认自己的 Alertmanager 目标
- **THEN** 脚本向 `/api/v2/alerts` 发送恰好十条关联告警，成功后只输出安全目标 host 与数量

#### Scenario: 显式对齐告警时间
- **WHEN** 用户提供带时区的 `--starts-at`
- **THEN** 十条告警使用该时间作为 `startsAt`，`endsAt` 为该时间加 2 小时

#### Scenario: 非法告警时间
- **WHEN** `--starts-at` 缺少时区或无法解析
- **THEN** 脚本在网络请求前失败且不发布任何告警

#### Scenario: 演示告警有效期 30 天
- **WHEN** 用户传 `--active-days 30`
- **THEN** 十条告警的 `endsAt` 为各自 `startsAt` 加 30 天

#### Scenario: 已有告警时 ensure 跳过
- **WHEN** `--ensure` 查询到当前已有 10 条活跃告警
- **THEN** 脚本不发送 POST，并输出已存在告警的安全摘要

#### Scenario: 未确认或目标非法
- **WHEN** 用户未确认目标，或 URL 缺少合法 HTTP(S) host、包含 userinfo/query/fragment
- **THEN** 脚本在网络请求前失败且不发布任何告警
