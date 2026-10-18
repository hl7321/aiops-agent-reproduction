# Spec Delta

## MODIFIED Requirements

### Requirement: CLS 权威参数由服务端确定性传递

当前运行时 SHALL 继续从 ignored 本地 JSON 深合并后的 `clsLogUpload.region` 与 `clsLogUpload.topicId` 取得可信默认值，不新增远端日志源发现或路由。Region 与 TopicId MUST 由服务端无条件注入，模型和客户端 MUST NOT 覆盖，且 MUST NOT 出现在模型可见的参数说明中。

SearchLog 的 `From`/`To` SHALL 由服务端依据告警时间与 `clsLogUpload.windowBeforeMinutes`（默认 15）和 `windowAfterMinutes`（默认 0）确定性计算：窗口起点为最早告警 `startsAt` 减去 before，终点为最晚告警 `startsAt` 加上 after。`From`/`To` MUST NOT 由模型生成，也 MUST NOT 出现在模型可见的参数说明中；告警缺少可解析的 `startsAt` 时 MUST 在调用 SearchLog 前以明确错误失败。

依赖前面步骤真实产出的字段 SHALL 由执行者在执行该步骤时提供，MUST NOT 在计划阶段预先写死。执行者 MUST 按字段性质区分来源：

- **计划保证的跨步配对**（SearchLog 的 Query 来自其必需的 query-builder 步骤产出、DescribeLogContext 的 Time/PkgId/PkgLogId 来自本轮已验证的 SearchLog 命中）MUST 由执行者**确定性绑定**，MUST NOT 交给模型生成，也 MUST NOT 出现在模型可见的参数说明中——这些是"搬运"而不是"判断"，交给模型只会让计划校验要求的步骤失去意义。
- **其余需要判断的字段**（返回条数、自然语言检索意图、其他工具自有的参数）SHALL 由执行者依据当前工具说明与前序产出生成。

无论来源如何，最终参数 MUST 通过该工具的真实 schema 校验后才可调用。

#### Scenario: 上下文参数装配

- **WHEN** SearchLog 产生一个有效命中且计划进入 DescribeLogContext
- **THEN** 系统从本地配置注入 Region/TopicId，执行者从该命中产出填入 Time/PkgId/PkgLogId，再经 schema 校验后才调用工具

#### Scenario: 本地默认值缺失

- **WHEN** 计划需要 SearchLog 或 DescribeLogContext，但 `clsLogUpload.region` 或 `clsLogUpload.topicId` 为空
- **THEN** 诊断在调用该 CLS 工具前以明确配置错误失败，不让模型猜测或从日志正文反推

#### Scenario: 模型提供了服务端权威字段

- **WHEN** 模型在执行参数里给出 `Region`、`TopicId`、`From` 或 `To`
- **THEN** 系统忽略这些取值并以服务端注入值为准，且它们不出现在模型可见的参数说明中

#### Scenario: 时间窗由告警时间派生

- **WHEN** 本轮只有一条告警且其 `startsAt` 为 T，窗口配置为 before=15、after=0
- **THEN** 实际调用 SearchLog 的 `From` 为 T−15 分钟、`To` 为 T，与模型输出无关

#### Scenario: 多告警时间窗覆盖全部告警

- **WHEN** 本轮包含多条告警且 `startsAt` 分别为 T1、T2（T1 < T2），窗口配置为 before=15、after=0
- **THEN** 实际窗口为 `[T1−15 分钟, T2]`，不按单条告警分别猜测

#### Scenario: 告警时间不可解析

- **WHEN** 本轮告警缺少 `startsAt` 或该值不是可解析的时间
- **THEN** 诊断在调用 SearchLog 前以明确错误失败，不退回模型自算时间窗

#### Scenario: 跨步骤参数由执行者填写

- **WHEN** 执行者执行一个需要前面步骤产出的步骤
- **THEN** 属于计划保证配对的字段被确定性绑定、其余字段由模型依据前序产出生成，全部通过该工具真实 schema 校验后才执行

#### Scenario: 绑定字段不接受模型取值

- **WHEN** 模型为已由执行者绑定的字段（例如 SearchLog 的 Query）给出别的取值
- **THEN** 执行者以绑定值为准，模型取值被忽略，且该字段不出现在模型可见的参数说明中
