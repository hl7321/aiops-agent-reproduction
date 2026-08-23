## Context

见 `proposal.md`。P20 已提供 import-safe 的 `generate_and_upload_cls_logs.py`、本地 JSON 深合并和 CLS SDK 注入边界；P10/P11 已提供文档上传与 durable indexing API；P20/P21 已提供 Alertmanager 输入与诊断链路。P25 不新增运行时服务，而是在 `scripts/` 建立可审计的真实演示数据入口。

三个动作都可能修改用户的外部系统，因此“执行 CLI + 显式确认目标”是权限边界。自动化不能读取 ignored 凭据或连接真实目标，应用 import/lifespan 也不得引用这些脚本。

## Goals / Non-Goals

**Goals:**

- 用单一纯 fixture catalog 固定十套 Java 电商故障，避免日志、告警和 SOP 各自复制并漂移。
- 保持 P20 CLS 脚本的旧 count 调用兼容，并增加明确的固定十场景 profile。
- 让 Alertmanager 和知识 API 的真实写入都经过显式 CLI、目标确认、有界 timeout 和可注入 transport。
- 在不执行外部写入的测试中证明数量、唯一性、关联一致性、安全内容、错误退出与 import-safety。

**Non-Goals:**

- 不自动启动 Compose、后端、CLS MCP、Qwen 或 Milvus，不自动执行真实 smoke。
- 不新增产品 endpoint、数据库表、前端页面、Compose service、真实客户样本或生产告警规则。
- 不承诺自动清理已发布告警、已上传 CLS 日志或已创建知识文档；执行前由用户确认目标和影响。

## Decisions

### 1. 共享 frozen fixture catalog 是唯一事实来源

新增 `scripts/java_ecommerce_aiops_fixtures.py`，以不可变 record 表达每套 incident，并暴露固定 tuple 与纯 builder：CLS records、Alertmanager payload、SOP filename/Markdown。所有稳定标识使用代码内显式常量，不在运行时随机生成；事件时间作为调用参数注入。

选择纯 Python 数据而非三份 JSON/YAML，是为了让字段约束、生成逻辑和类型检查在同一处完成，同时避免脚本分别维护映射。备选的运行时随机 ID 无法跨进程关联，也无法稳定重放，因此拒绝。

### 2. Java profile 固定十套，quant profile 保留 count

现有 CLS CLI 增加 `--profile quant|java-ecommerce`，默认 `quant`。为区分“用户没写 count”与“显式为 Java 提供 count”，`--count` 的 argparse 默认改为 `None`，在 quant 路径再应用旧默认 20；Java 路径只接受 `count is None` 并固定生成十套 records。底层现有 `generate_log_records`、`upload_logs(settings, count)` API 保持兼容，新增 profile-aware 生成/上传函数负责选择 records。

备选是另建同名或 Java 专用 CLS 上传脚本，会复制 P20 的 SDK、配置与脱敏边界，违反单脚本要求，因此拒绝。

### 3. 写入脚本使用可注入同步 HTTP transport

Alertmanager 与 SOP seed 均为人工串行 CLI，使用标准库 HTTP 实现生产 transport，并把 `request(method, url, headers, body, timeout)` 抽象成 Protocol。测试传入 fake transport，断言真实序列化 payload、调用顺序、timeout 和失败语义；模块 import 不实例化 transport。

备选是把脚本放进 FastAPI service 或后台 job，会让应用启动/运行时更容易误触发外部写入；备选的全局 httpx client 也违反 import-safety，因此拒绝。

### 4. Alertmanager 目标由 CLI 明确提供

`publish_java_ecommerce_alerts.py` 要求 `--alertmanager-url` 和 `--confirm-target`，规范化 base URL 后只允许向其 `/api/v2/alerts` 发布。拒绝 userinfo、query、fragment，timeout 限制在 1..300 秒。payload 使用固定 labels/annotations，startsAt/endAt 由注入的 UTC 时间生成；incident/trace/SOP 字段全部来自 catalog。

不从 deployment-global `prometheusAlerts.sources` 自动挑选写入目标，因为 source 列表也可能包含只读 Prometheus，且自动选择会模糊用户对副作用目标的确认。

### 5. SOP seed 复用真实认证和知识/index API

`seed_java_ecommerce_aiops_sops.py` 只读取 `project.json` 与 `user.project.json` 深合并后的 `aiopsDemo`，要求 `--confirm-target`。流程固定为登录、读取唯一默认 KB、逐份 multipart 上传、显式创建 index task、按配置间隔轮询到 succeeded。上传使用 `fixed-character` 默认策略；Markdown 内嵌可检索的 `knowledgeType: aiops-sop` 与关联字段，文件上传 metadata 通过已有文档合同可追溯。

脚本不会直接写 SQLite/Milvus，也不会调用内部 service，从而保持认证、owner scope、重复 hash 和 durable indexing 的现有权威边界。冲突不做静默 overwrite，避免覆盖用户已有 SOP。

### 6. 错误与输出采用阶段化安全摘要

三脚本统一在非确认、非法目标、非 2xx、响应 envelope 无效、索引失败或 timeout 时非零退出。错误只包含阶段、稳定 incident id、HTTP status 和安全服务 host；不打印 bearer、email/password、CLS secret、响应正文或完整 URL query。成功输出只包含安全数量、request id/host 和必要的非敏感任务计数。

备选的“尽量继续并最终打印部分成功”会让用户误以为十套演示已完整就绪，因此主流程采取 fail-fast；已完成的外部写入可能存在，文档明确没有跨系统事务。

### 7. 真实 smoke 是单独的人工顺序，不属于门禁

文档给出 CLS 发布、CLS 查询确认、SOP seed/index、Alertmanager 发布、诊断与证据报告核对的顺序，并要求逐个确认目标。P25 门禁只执行纯 builder、fake transport、CLI 参数和 import-safety 测试。真实 smoke 未执行时明确记录，不能用 fake 结果宣称可检索或端到端成功。

## Risks / Trade-offs

- [固定 incident 会在重复执行时产生重复外部数据] → 标识稳定便于关联，执行前明确提示目标与重复影响；脚本不声称幂等清理。
- [SOP seed 过程中部分成功后失败] → 输出失败 incident 和阶段，依赖现有 hash 冲突阻止无声重复；不宣称跨系统事务。
- [Alertmanager POST 成功但稍后告警过期] → 使用有界 endAt，真实 smoke 紧接发布执行；fixtures 本身不承担长期告警管理。
- [标准库 multipart/HTTP 实现容易出现边界错误] → builder 与 transport 分离，自动化断言 Content-Type、envelope、路径、payload 和失败退出。
- [文档中的 rootCause 是演示先验] → 明确标记为 synthetic fixture/SOP，不把其当作真实诊断证据；产品报告仍只能基于真实工具返回的证据。

## Migration Plan

1. 先增加纯 fixture contract tests，确认主线尚无十场景实现并观察 RED。
2. 实现共享 catalog/builders，再扩展 CLS profile 并保持 P20 tests 全绿。
3. 为 Alertmanager 与 SOP seed 分别先写失败测试，再实现显式 CLI 和 fake transport 边界。
4. 更新脚本文档与 OpenSpec，运行 backend/OpenSpec/脚本语法门禁；不执行真实写入。
5. 验证通过后同步主规格、归档并提交 main。回滚只需移除新增脚本/测试和还原 CLS profile 扩展；外部已写数据需由用户在各自系统人工处理。
