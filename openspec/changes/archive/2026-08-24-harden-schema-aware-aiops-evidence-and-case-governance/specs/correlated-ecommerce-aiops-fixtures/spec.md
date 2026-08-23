## MODIFIED Requirements

### Requirement: CLS 脚本扩展既有入口而不复制实现
仓库 SHALL 继续只提供一个 `generate_and_upload_cls_logs.py`。它 MUST 保持既有量化 profile/count 调用兼容，并为固定十套 `java-ecommerce` incident 分别生成稳定、互相隔离的 context flow 和多条有序日志，使 SearchLog 的真实命中可返回非空 Time/PkgId/PkgLogId 并用于后续 DescribeLogContext。每条日志 MUST 保持完整关联字段；脚本只有在用户显式 CLI 调用并确认自己的 CLS 目标时才可创建 SDK client 和上传。

#### Scenario: Java CLS 显式上传
- **WHEN** 用户选择 java-ecommerce profile、确认目标且本地 CLS 配置有效
- **THEN** 脚本为十套 incident 上传相互隔离的多行上下文，并只输出安全数量与 request id

#### Scenario: 同一 incident 上下文稳定
- **WHEN** SearchLog 命中任一 Java incident 的错误日志
- **THEN** 结果含可用 Time/PkgId/PkgLogId，DescribeLogContext 能读取同 incident 的前后有序日志而不混入其他 incident

#### Scenario: 量化 profile 兼容
- **WHEN** 用户沿用既有 count 调用或显式选择量化 profile
- **THEN** 脚本仍接受 1..100 的 count 并生成原有有界日志，不改变既有 CLS 路由与脱敏语义

### Requirement: 外部副作用与真实 smoke 必须由用户显式触发
导入脚本模块、运行单元测试、启动 FastAPI/Vue/Compose 或执行普通工程门禁 MUST NOT 上传 CLS、发布告警或 seed SOP。自动测试 SHALL 使用 fake SDK/HTTP/API 边界验证 payload、context flow 和错误；完整真实 smoke 只有在用户确认各自目标后人工执行，并 MUST 验证 `发布→SearchLog 原始命中→DescribeLogContext→SOP 索引→告警诊断→可信证据报告→人工认可→案例索引→再检索`，未执行时 MUST 如实记录。

#### Scenario: import 与普通门禁
- **WHEN** 测试导入三个脚本及共享 fixture 模块，或运行普通启动与门禁
- **THEN** 不创建外部 client、不读取真实凭据、不发起网络请求且不产生外部写入

#### Scenario: 未执行真实 smoke
- **WHEN** CLS、Alertmanager、知识索引或诊断环境不完整，或用户未确认目标
- **THEN** 验证报告明确标记真实 smoke 未执行，不以 fake 测试替代真实联调结论
