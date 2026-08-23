## ADDED Requirements

### Requirement: CLS 日志 CLI 支持兼容的 profile 选择
CLS 日志 CLI SHALL 支持 `quant` 与 `java-ecommerce` profile。未显式提供 profile 的既有 `--count` 调用 MUST 保持 `quant` 行为；`quant` 允许 1..100 的有界 count，`java-ecommerce` 固定使用十套权威关联 fixture 且 MUST 拒绝 count。两个 profile 均复用相同的本地 JSON 配置、SDK 路由、目标确认和凭据脱敏边界。

#### Scenario: 既有 count 调用保持兼容
- **WHEN** 用户只提供原有 `--count 20 --confirm-target`
- **THEN** CLI 继续生成并上传二十条量化 profile 日志，不要求新增参数

#### Scenario: Java profile 固定十套
- **WHEN** 用户提供 `--profile java-ecommerce --confirm-target` 且未提供 count
- **THEN** CLI 为十套权威 Java 电商 fixture 生成日志并上传，数量固定为十

#### Scenario: profile 参数冲突
- **WHEN** 用户为 `java-ecommerce` profile 提供任意 count
- **THEN** CLI 在创建 SDK client 前明确拒绝，不静默忽略 count
