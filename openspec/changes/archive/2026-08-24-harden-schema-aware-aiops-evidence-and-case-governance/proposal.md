## Why

当前 AIOps 运行时会把本轮真实发现的全部 MCP 工具交给 Planner，但只有 `SearchLog` 具有专门的参数收敛，通用证据解析也无法可靠接收 `TextToSearchLogQuery`、`DescribeLogContext` 等合法工具结果。这会让“工具已发现并调用”与“输出可验证、可持续推进、可形成可信报告”之间出现断层，同时不确定报告仍可能自动进入案例知识，跨诊断任务也缺少稳定去重。

## What Changes

- 保留 owner-scoped MCP 动态发现作为第一层安全白名单，新增只读、可验证、可形成证据的 AIOps 能力白名单；Planner 只能看到二者交集。
- 为 CLS 日志诊断建立能力依赖图：当前 Profile 仍要求一个真实 `SearchLog`；Query 尚未由服务端可信生成/校验时才要求 `TextToSearchLogQuery`；只有计划结论需要时序上下文且命中提供定位字段时才要求 `DescribeLogContext`。
- 所有进入 AIOps policy 的工具都必须校验输入；证据型工具必须有显式输出 adapter，查询准备等辅助工具必须有中间产物 adapter。核心 CLS 工具使用 Pydantic 输入、输出与跨步结果模型。
- 保留 ignored 本地 JSON 中 `clsLogUpload.region/topicId` 作为当前诊断运行时的可信默认值；不新增日志源注册表、远端路由或部署映射。
- 增加最多三次的分类重试与纠错；Pydantic 负责发现结构错误，独立错误策略区分可修正、临时和永久错误。必需证据无法取得时不得生成可信结论，Replanner 只能选择其他已登记真实证据或形成不可提升的证据不足结果。
- 区分可信模型报告、证据不足说明和执行失败说明；只有完整证据、无不确定性且经过当前 owner 明确认可的报告才能提升为案例知识。
- 为跨诊断任务的案例沉淀增加稳定 fingerprint、canonical case 和来源关系；精确重复只追加 provenance，语义相似只提示人工处理，不自动重复写入向量库。
- 调整十套 Java 电商 fixture，使每个 incident 具有稳定、隔离且可被 `DescribeLogContext` 使用的多行上下文。
- 前端展示工具能力、重试、证据门禁、报告可信状态和显式知识提升，不渲染原始 MCP JSON。

## Capabilities

### New Capabilities

- `schema-aware-aiops-tool-execution`: 定义动态发现与 AIOps 能力白名单交集、所有允许工具的输入验证、证据/辅助输出 adapter、条件依赖和有界纠错。

### Modified Capabilities

- `aiops-diagnosis-and-evidence`: 收紧能力依赖、证据充分性、Replanner、失败语义和报告可信门禁，同时避免把 DescribeLogContext 误设为所有诊断的绝对前置。
- `diagnosis-case-persistence`: 将成功即自动沉淀改为人工认可后的显式提升，并增加跨任务 canonical case 去重和 provenance。
- `user-feedback-collection`: 明确诊断报告反馈可作为可信案例提升的 owner-scoped 审批依据。
- `correlated-ecommerce-aiops-fixtures`: 使十套 CLS fixture 产生可用于 SearchLog 后续上下文查询的稳定多行日志。
- `final-aiops-workspace`: 展示 Schema 校验、重试、严格证据状态、报告认可和案例去重交互。

## Impact

- 后端：`super_ai.aiops` Planner/Executor/Replanner/report、MCP 工具策略与适配、诊断持久化、案例服务、feedback 集成和 fixture 脚本。
- 数据库：报告可信/提升状态、canonical case fingerprint 与 case source provenance 的 Alembic 迁移。
- contracts/OpenAPI：诊断步骤 attempt/错误分类、报告可信状态、案例提升与重复候选 DTO。
- 前端：AIOps store/client/timeline/report feedback 与案例提升 UI。
- 配置：继续消费现有本地 JSON `clsLogUpload.region/topicId`，不改变配置来源和浏览器公开边界。
- 测试与文档：增加真实官方 Schema 兼容样本、条件能力链、替代证据与不足结果、去重并发、fixture context 和全量门禁；外部 CLS smoke 仍只在用户明确授权时执行。
