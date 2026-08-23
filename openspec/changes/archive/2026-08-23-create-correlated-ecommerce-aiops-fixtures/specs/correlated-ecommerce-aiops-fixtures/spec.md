## Purpose

本能力提供十套合成、安全、稳定关联的 Java 电商 AIOps 演示输入，并以人工显式 CLI 串联真实 CLS、Alertmanager、知识索引和后续诊断链路。

## ADDED Requirements

### Requirement: Java 电商 profile 固定提供十套互异故障
`java-ecommerce` profile SHALL 固定生成且仅生成十套 incident，分别覆盖 payment-service 支付网关超时、inventory-service 库存锁等待、order-service 数据库连接池耗尽、cart-service Redis 延迟、api-gateway 结算熔断、promotion-service CPU 饱和、order-event-consumer Kafka lag、product-search-service Elasticsearch timeout、auth-service JWK refresh failure、fulfillment-service 外部供应商 503。Java profile MUST NOT 接受 count 改变数量。

#### Scenario: 固定故障目录
- **WHEN** 调用方读取 Java 电商 profile
- **THEN** 返回顺序稳定的十套 incident，服务和故障类型逐项匹配权威目录且不存在第十一套

#### Scenario: Java profile 拒绝量化数量
- **WHEN** 用户为 Java profile 同时提供 count
- **THEN** CLI 在任何网络 client 创建前明确失败，不截断或复制十套目录

### Requirement: 每套 fixture 具有稳定完整的关联字段
每套 incident SHALL 固定包含唯一 `incident_id`、`trace_id`、`service`、`alertname`、`sop_id`、`logger`、`exception`、`dependency`、metric/threshold、symptom、rootCause、investigation、recovery 与 verification。三个输出面中的关联字段 MUST 来自同一 fixture，且十套之间的 incident、trace、service、alertname 与 SOP 标识均互不重复。

#### Scenario: 跨载荷关联一致
- **WHEN** 为任一 fixture 生成 CLS records、Alertmanager alert 和 Markdown SOP
- **THEN** 三者携带相同的 incident、trace、service、alertname 与 SOP 标识，且故障症状、依赖和处置语义一致

#### Scenario: 标识稳定
- **WHEN** 在不同进程和不同时间重复生成同一 profile
- **THEN** 十套 incident/trace/SOP 标识及其目录顺序保持不变，只有显式允许的事件时间字段可变化

### Requirement: 合成数据安全且可索引
fixtures SHALL 只包含合成的 Java 运维数据，不得包含客户数据、真实 token、真实凭据、password、secret 或可复用认证信息。每份 SOP MUST 为 UTF-8 Markdown，包含可检索的 incident/service/alert/exception/dependency/metric、症状、根因、排查、恢复和验证文本，并携带 `knowledgeType=aiops-sop` 的可追溯上传 metadata。

#### Scenario: 安全内容扫描
- **WHEN** 序列化十套 fixture 及其日志、告警、SOP
- **THEN** 内容不包含凭据字段或真实客户标识，且日志 message 和标签值均有界

#### Scenario: SOP 可索引内容
- **WHEN** 为十套 fixture 生成 Markdown SOP
- **THEN** 每份文档非空、文件名唯一，并包含该 incident 的关联字段及 investigation/recovery/verification 章节

### Requirement: CLS 脚本扩展既有入口而不复制实现
仓库 SHALL 继续只提供一个 `generate_and_upload_cls_logs.py`。它 MUST 保持既有量化 profile/count 调用兼容，并增加固定十套的 `java-ecommerce` profile；Java profile 的每套 CLS 日志 MUST 包含完整关联字段。脚本只有在用户显式 CLI 调用并确认自己的 CLS 目标时才可创建 SDK client 和上传。

#### Scenario: Java CLS 显式上传
- **WHEN** 用户选择 `java-ecommerce` profile、确认目标且本地 CLS 配置有效
- **THEN** 脚本上传十套相互关联的日志并只输出安全数量与 request id

#### Scenario: 量化 profile 兼容
- **WHEN** 用户沿用既有 count 调用或显式选择量化 profile
- **THEN** 脚本仍接受 1..100 的 count 并生成原有有界日志，不改变既有 CLS 路由与脱敏语义

### Requirement: Alertmanager 发布必须显式选择并确认目标
仓库 SHALL 提供 `publish_java_ecommerce_alerts.py`，仅通过显式 CLI 向用户给出的 HTTP(S) Alertmanager base URL 发布十条 v2 alerts。URL MUST 有 host、拒绝 userinfo；脚本 MUST 要求显式确认目标，设置有界 timeout，并在非 2xx、网络或响应错误时非零退出且不得声称成功。

#### Scenario: 发布十条真实告警
- **WHEN** 用户显式指定并确认自己的 Alertmanager 目标
- **THEN** 脚本向 `/api/v2/alerts` 发送恰好十条关联告警，成功后只输出安全目标 host 与数量

#### Scenario: 未确认或目标非法
- **WHEN** 用户未确认目标，或 URL 缺少合法 HTTP(S) host、包含 userinfo/query/fragment
- **THEN** 脚本在网络请求前失败且不发布任何告警

### Requirement: SOP seed 通过真实认证知识 API 和 durable indexing
仓库 SHALL 提供 `seed_java_ecommerce_aiops_sops.py`，从本地 JSON 深合并后的 `aiopsDemo` 读取 backendBaseUrl/email/password/pollIntervalSeconds/indexWaitSeconds，通过真实登录、默认知识库读取、multipart Markdown 上传和显式 index-task 创建来 seed 十份 SOP。脚本 MUST 在有界时间内轮询领域 index task，只有十份均为 succeeded 才能声称完成；冲突、认证、上传、索引失败或超时 MUST 非零退出并脱敏。

#### Scenario: 成功 seed 与索引
- **WHEN** 用户显式确认 backend 目标且真实 API、凭据、Qwen 和 Milvus 可用
- **THEN** 脚本上传十份 SOP、为每份创建 index task、等待十项 succeeded 后输出安全完成摘要

#### Scenario: 失败不冒充成功
- **WHEN** 任一登录、知识库、上传、index task 创建、轮询或 timeout 失败
- **THEN** 脚本非零退出，指出安全阶段与 incident，不输出全部成功声明

### Requirement: 外部副作用与真实 smoke 必须由用户显式触发
导入脚本模块、运行单元测试、启动 FastAPI/Vue/Compose 或执行普通工程门禁 MUST NOT 上传 CLS、发布告警或 seed SOP。自动测试 SHALL 使用 fake SDK/HTTP/API 边界验证 payload 和错误；“发布→CLS 查询→SOP 索引→告警诊断→证据报告”的真实 smoke 只有在用户确认各自目标后人工执行，未执行时 MUST 如实记录。

#### Scenario: import 与普通门禁
- **WHEN** 测试导入三个脚本及共享 fixture 模块，或运行普通启动与门禁
- **THEN** 不创建外部 client、不读取真实凭据、不发起网络请求且不产生外部写入

#### Scenario: 未执行真实 smoke
- **WHEN** CLS、Alertmanager、知识索引或诊断环境不完整，或用户未确认目标
- **THEN** 验证报告明确标记真实 smoke 未执行，不以 fake 测试替代真实联调结论
