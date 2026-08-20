## Context

见 `proposal.md`。当前 `project.template.json` 已有旧的单 `prometheusAlerts.baseUrl` 和 `clsLogUpload` 占位，FastAPI 通过 `create_configured_app(project_path, user_path)` 显式加载本地 JSON，外部 client 都遵循运行期工厂/依赖注入。Alertmanager 已由五服务 Compose 托管，但 P20 不改变 Compose。共享合同由 TypeScript、Pydantic 与机器可读 manifest 三方测试约束。

官方接口边界已经核对：Prometheus v1 活跃告警为 `GET /api/v1/alerts`；Alertmanager v2 为 `GET /api/v2/alerts`，其 status state 包含 active/suppressed/unprocessed；腾讯官方 Python CLS SDK 使用 `LogClient(endpoint, accessKeyId, accessKey)` 和 `put_log_raw(topicId, LogGroupList)`。项目仍禁止通过 OS 环境变量读取配置。

## Goals / Non-Goals

**Goals:**

- 建立可注入、import-safe、支持部分失败的多来源告警读取边界。
- 在 API 层只暴露稳定标准告警 items，使 P21 不依赖 provider 私有 payload。
- 将 CLS 外部写入隔离为人工显式 CLI，并让 payload、count、配置与输出可自动验证。
- 保持 source 是 deployment-global 配置，同时让 endpoint 仍经过认证保护。

**Non-Goals:**

- 不把告警或 source 写入 SQLite，不提供 source CRUD 或用户级 source。
- 不实现告警轮询后台任务、诊断、报告、case、处置或 remediation。
- 不在 Compose 增加 Prometheus、应用服务或 CLS 服务。
- 不在本 change 自动执行任何真实 CLS 写入；真实告警读取 smoke 也只在用户配置的目标可用时如实记录。

## Decisions

### 1. 使用 typed source 列表替换旧单 baseUrl

`prometheusAlerts.sources` 是判别联合：`name`、`type`、`baseUrl`、`timeoutSeconds` 与 nullable `basicAuth`。名称在 deployment 内唯一，URL 只允许 HTTP(S)、必须有 host、拒绝 userinfo；Basic Auth 必须 username/password 同时非空或整体缺省。模板提供本地 Alertmanager v2 的无凭据示例，user template 保持同构空凭据。

备选方案是保留单 baseUrl 并根据 URL 猜 provider；它无法同时聚合两个 API，也会把协议选择隐藏在脆弱推断里，因此拒绝。

### 2. Provider 负责解析，Aggregator 只负责并发与失败策略

`AlertProvider` Protocol 只暴露 source 与 `fetch_active_alerts()`。Prometheus/Alertmanager provider 各自拥有路径、payload validation 和状态映射；具体 httpx client 由 request-scoped factory 创建并关闭。Aggregator 使用 `asyncio.gather(..., return_exceptions=True)` 并发读取，至少一个 source 成功即返回所有成功 items；空数组也是成功结果。零 source 或全失败抛稳定 AppError 503。

备选方案是由一个 service 根据大量 if/else 处理所有 payload；这会把协议解析、client 生命周期和降级策略耦合，不利于 P21 测试与新增 provider，因此拒绝。

### 3. 标准状态保留语义而不复制 provider 全状态模型

公共 status 为 `pending|firing|suppressed|unprocessed`。Prometheus pending/firing 原样映射；Alertmanager active 映射为 firing，suppressed/unprocessed 原样映射。原始单条记录保存在 `rawContext`，因此不会丢失 Alertmanager 的 silencedBy/inhibitedBy 等细节。service/severity 来自 labels，缺失时为 null，不制造 `unknown` 值。

备选方案是只统一为 active/inactive；它会丢失 pending/suppressed 等诊断信号。另一方案是直接暴露两套 provider DTO，会把 P21 与上游格式绑定，均拒绝。

### 4. 认证只保护读取，不改变 source 所有权

路由先解析 `CurrentUser`，再创建 provider/client 并聚合。因此未认证请求不会访问 deployment source。认证用户看到同一项目配置的实时告警；响应不增加 ownerUserId、tenantId 或 providerStatuses。这里的 403 只作为共享受保护 path 模式保留，当前 endpoint 没有 user-owned parent 可触发该语义。

备选方案是给每个用户复制 source 配置；它违背用户明确的 deployment-global 边界，并增加凭据复制风险，因此拒绝。

### 5. CLS 脚本分为纯配置/生成边界与延迟 SDK 适配

`scripts/generate_and_upload_cls_logs.py` 是自包含 PEP 723 脚本，提供可导入纯函数：本地 JSON 深合并、typed settings 解析、endpoint/count 校验、结构化记录生成、protobuf group 构造与 `upload_logs(settings, count, client_factory)`。它使用独立依赖环境和单独 lock，官方 SDK 只在默认 protobuf/client factory 被显式调用时延迟 import；应用包不 import 脚本。`LogClient` 只接收 endpoint/secretId/secretKey，`put_log_raw` 只接收 topicId/groups；logsetId 不进入 SDK 调用。CLI 还要求显式 `--confirm-target`，避免仅因复制命令就产生写入。

备选方案是增加 FastAPI 上传 endpoint 或 lifespan seed；两者都会让外部写入更容易被误触发，且扩大攻击面，因此拒绝。

### 6. 生成内容固定、安全且有界

CLI `--count` 默认 20，允许 1..100。每条日志使用固定字段目录 region/service/severity/level/traceId/timestamp/message，message 从有限的运维模拟模板选择并限制长度；不接受任意日志正文或 secret 参数。stdout 只输出安全数量与 request id；异常经过当前 secretId/secretKey 替换。凭据仅从显式本地 JSON 读取，不接受环境变量或命令行 secret。

备选方案是允许用户通过 CLI 传任意 message/JSON；它难以证明无敏感信息，超出“安全日志生成工具”范围，因此拒绝。

### 7. 隔离依赖和 import-safety

官方 `tencentcloud-cls-sdk-python==1.0.4` 强制 `protobuf<4` 与 `python-snappy<=0.6.0`，而 backend 的 pymilvus 3 强制 `protobuf>=5.27.2`，因此两者不能共享 `apps/backend` 的 `pyproject.toml/uv.lock`。脚本使用 PEP 723 依赖元数据与 `generate_and_upload_cls_logs.py.lock` 隔离解析；backend 依赖图保持不变。模块 import、FastAPI factory 与测试收集期间只定义类型/函数，不创建 httpx/SDK client、不读取 ignored 配置、不联网。自动化通过 fake HTTP/SDK 边界验证参数；真实脚本环境若在 macOS ARM 构建旧 python-snappy，需要先由用户自行安装系统 Snappy 开发库，门禁不得自动修改系统环境。

## Risks / Trade-offs

- [rawContext 可能包含部署标签中的业务敏感信息] → endpoint 必须认证，日志禁止输出 payload；P21 只按需要消费，当前不持久化。
- [部分失败会让调用者看不到失败 source] → 按用户要求成功响应不增加 provider status；服务端只记录安全 source name/失败类别，不记录 URL、认证或响应正文。
- [Alertmanager active 映射为 firing 是语义归一化] → rawContext 保留原始 active，合同明确映射规则。
- [真实 API 版本或 payload 漂移] → Pydantic/显式解析失败只影响对应 source；全失败显式 503，禁止静默 fallback。
- [CLS SDK 异常文本可能回显参数] → 所有用户可见输出先按当前 secretId/secretKey 脱敏；自动化覆盖异常含凭据场景。
- [官方 SDK 旧依赖与 backend/Mac ARM 不兼容] → PEP 723 单独锁隔离 protobuf；真实运行的系统 Snappy 前置条件只记录、不在门禁中自动安装。

## Migration Plan

1. 更新两个模板，把旧 `prometheusAlerts.baseUrl/username/password` 迁移为 `sources`；ignored 本机配置由使用者按新结构迁移，模板凭据继续为空。
2. 为独立脚本生成 PEP 723 lock；先以 fake SDK/HTTP 完成自动化，不连接外部服务，也不修改 backend lock。
3. 注册 typed settings、alert router 与配置化 app factory；未配置 source 时 endpoint 明确 503，应用其他能力仍可启动。
4. 运行 contracts/backend/OpenSpec 门禁。真实 Prometheus/Alertmanager 只读 smoke 在目标可用时执行；真实 CLS 写入只有用户确认自己的 endpoint/topic 后才执行。
5. 回滚时移除 router/settings 注入与脚本依赖并恢复模板；无数据库迁移、无持久数据回滚。
