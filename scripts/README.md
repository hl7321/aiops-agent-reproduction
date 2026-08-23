# 脚本目录

本目录用于跨 workspace 的可重复维护脚本。`check_api_contract_boundaries.py` 会检查应用生产源码，阻止在共享合同之外复制 SSE 事件字面量或直接拼装 HTTP envelope；仓库 pytest 门禁会用受控 fixture 和当前仓库执行该脚本。

## 人工生成并上传 CLS 日志

`generate_and_upload_cls_logs.py` 是独立的人工工具，不会被应用启动、模块导入或测试自动执行。它使用脚本自己的 PEP 723 依赖和 lock，避免腾讯 CLS SDK 的旧版 protobuf 约束污染后端依赖图。

凭据和目标只能填写在被 Git 忽略的 `config/user.project.json` 的 `clsLogUpload` 中；脚本先读取 `config/project.json`，再用用户配置递归深合并。禁止用环境变量传入项目配置，也禁止提交 `secretId`、`secretKey`。`region` 会写入每条日志，`logsetId` 只供人工核对，SDK 实际路由由 HTTPS `endpoint` 决定，上传目标为 `topicId`。

真实执行会向外部 CLS 写入数据。必须先人工确认 endpoint、region、logsetId、topicId 属于自己的目标，再显式运行：

```bash
uv run --locked --script scripts/generate_and_upload_cls_logs.py \
  --count 20 \
  --confirm-target
```

`count` 只能为 1 到 100。脚本只生成有界、无密钥的结构化样例日志，控制台只输出数量和 requestId，不打印凭据。macOS 若在首次创建脚本隔离环境时无法构建 `python-snappy`，需要先由使用者自行安装 Snappy 开发库；这不影响后端安装、启动或自动化门禁。

## 十套 Java 电商 AIOps 关联 fixtures

`java_ecommerce_aiops_fixtures.py` 固定提供十套合成故障，覆盖 payment、inventory、order、cart、gateway、promotion、Kafka consumer、Elasticsearch、auth JWK 和 fulfillment vendor。每套使用稳定且唯一的 incident、trace、service、alertname 与 SOP id，同一份纯 catalog 同时生成 CLS records、Alertmanager alerts 和 Markdown SOP。内容不含客户数据、真实 token 或凭据。

三个写入动作都只会在用户显式执行对应 CLI 并确认自己的目标后发生。导入模块、启动应用、启动 Compose 和运行自动化测试不会上传日志、发布告警或 seed SOP。

### 1. 上传 CLS 日志

现有脚本仍是唯一 CLS 上传入口。旧量化调用保持兼容，默认 profile 为 `quant`，`count` 仍限制在 1..100：

```bash
uv run --locked --script scripts/generate_and_upload_cls_logs.py \
  --count 20 \
  --confirm-target
```

固定十场景使用 `java-ecommerce`，不得同时提供 `--count`：

```bash
uv run --locked --script scripts/generate_and_upload_cls_logs.py \
  --profile java-ecommerce \
  --confirm-target
```

执行前必须逐项核对 ignored `config/user.project.json` 中 `clsLogUpload` 的 endpoint、region、logsetId 和 topicId 属于用户自己的目标。脚本不会自动查询 CLS 验证写入。

### 2. 发布 Alertmanager 告警

下面命令会向明确给出的 Alertmanager `/api/v2/alerts` 真实发布十条告警。目标 URL 只允许无 userinfo/query/fragment 的 HTTP(S) base URL：

```bash
python scripts/publish_java_ecommerce_alerts.py \
  --alertmanager-url http://127.0.0.1:9093 \
  --timeout-seconds 10 \
  --confirm-target
```

脚本不从只读 `prometheusAlerts.sources` 猜测写入目标，也不会启动 Alertmanager。非 2xx 或网络失败会非零退出，且不会回显响应正文。

### 3. 通过真实 API seed 并索引 SOP

先在 ignored `config/user.project.json` 的 `aiopsDemo` 填写真实本机 backendBaseUrl、email 和 password，并确保后端、durable worker、Qwen embedding 与 Milvus 已就绪。然后显式执行：

```bash
python scripts/seed_java_ecommerce_aiops_sops.py --confirm-target
```

脚本会真实登录、读取当前用户的默认知识库、逐份上传 Markdown、逐份创建 index task，并按 pollIntervalSeconds 在 indexWaitSeconds 硬上限内等待十项全部 succeeded。hash 冲突、认证失败、索引失败或超时都会非零退出；脚本不会覆盖现有文档，也不直接写 SQLite 或 Milvus。

### 人工端到端 smoke

真实 smoke 不属于普通门禁，必须由用户逐目标确认后按以下顺序人工执行：

1. 上传 `java-ecommerce` CLS profile，并通过用户自己的 CLS 查询确认稳定 incident/trace 可检索。
2. seed 十份 SOP，确认十个 durable index task 均 succeeded，并通过知识检索确认对应 SOP 命中。
3. 向用户明确选择的 Alertmanager 发布十条告警，确认 `/aiops/alerts/active` 返回关联 labels。
4. 从其中一条真实告警发起诊断，核对 SearchLog、知识引用、证据链与报告中的 incident/trace/service/SOP 关联。

任何目标未确认或真实服务未就绪时都应停止；fake 单测只能证明 payload 和失败边界，不能替代“CLS 可查询、SOP 可检索、诊断端到端成功”的结论。
