## Why

当前 AIOps 链路虽已能消费真实告警、CLS 日志和知识文档，但缺少一组可重复、可追溯且不会泄露真实业务数据的端到端演示输入。P25 需要把十类典型 Java 电商故障用稳定关联键串联起来，同时把所有真实外部写入限制在用户显式执行的 CLI 中。

## What Changes

- 新增十套固定且互不重复的 Java 电商故障 fixture，统一关联 CLS 日志、Alertmanager 告警和 Markdown SOP。
- 扩展现有 `generate_and_upload_cls_logs.py`，增加固定十场景 `java-ecommerce` profile，同时保持原有量化 profile/count 调用兼容。
- 新增显式 Alertmanager 发布脚本，只向用户明确指定并确认的 HTTP(S) Alertmanager 目标发布十条告警。
- 新增显式 SOP seed 脚本，通过真实认证 API 上传十份 Markdown、创建 durable index task 并在有界时间内等待结果。
- 新增纯数据/生成边界与自动化测试，验证数量、唯一性、跨载荷关联、安全内容、失败退出和 import 无副作用。
- 补充人工真实 smoke 的执行顺序和诚实记录要求；普通启动、测试和门禁不执行 CLS、告警或 SOP 外部写入。

## Capabilities

### New Capabilities

- `correlated-ecommerce-aiops-fixtures`: 定义十套 Java 电商故障 fixtures、三类显式副作用脚本、跨载荷关联、安全边界和真实 smoke 约定。

### Modified Capabilities

- `active-alert-and-cls-log-inputs`: 扩展既有 CLS CLI 的 profile 语义，固定 Java 十场景并保持量化 count 兼容。

## Impact

- 影响 `scripts/` 下的 CLS 上传工具、共享 fixture 模块、新增告警发布与 SOP seed 工具及脚本文档。
- 影响 backend 脚本测试和 OpenSpec 主规格；不新增产品 API、数据库迁移或 Compose 服务。
- 真实 CLS、Alertmanager 和知识库写入仍由用户显式 CLI 调用触发，本 change 的自动化只使用 fake HTTP/SDK/API 边界。
