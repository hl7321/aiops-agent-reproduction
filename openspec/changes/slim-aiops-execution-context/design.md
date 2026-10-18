# Design

## Context

见 `proposal.md - Why`。当前 executor 的 `_step_argument_context` 会把整条告警（含 `rawContext`）和全部非告警证据重复塞进每一步；工具目录由 f-string 直接插值，得到 Python `repr`。需求见 `specs/schema-aware-aiops-tool-execution/spec.md`。

## Goals / Non-Goals

**Goals：**

- 让 planner、executor、report 的上下文职责清晰；
- 降低每步重复 token，同时不改变工具参数注入与最终结果；
- 工具目录成为可解析的 JSON，并保留官方约束。

**Non-Goals：**

- 不改 planner/report 的上下文规模与内容；
- 不改工具注册、重试、报告信任状态；
- 不改 API、SSE 或数据库。

## Decisions

### 1. 三层上下文固定职责

- planner：完整告警 + SOP + 完整工具目录；
- executor：当前工具说明 + 整份计划 + 最小告警摘要 + 当前步骤需要的前序产出 + 上一次错误；
- report：完整证据与执行结果（保持现状）。

备选：只删掉"重复证据"但仍传完整告警。告警原文里的 `rawContext` 占了大部分体积，且与执行无关，因此一并裁剪。

### 2. 最小告警摘要的字段边界

摘要只保留：`alertName`、`service`、`severity`、`startsAt`、`labels` 中的 `incident_id`/`trace_id`/`alertname`/`sop_id`、`annotations.summary` 与 `annotations.rootCause`（各限 500 字）。不包含 `rawContext`、`fingerprint`、`receivers`、`generatorURL`。

备选：完全不传告警。DescribeTopics 与 TextToSearchLogQuery 仍需要服务名/异常语义，完全不传会让 executor 重新猜。

### 3. 前序产出按需、限量

默认只传上一步的产出，单段上限 2000 字；SearchLog 的 Query/From/To/Region/TopicId 已由服务端绑定，因此 SearchLog 步骤默认不传任何前序证据。未来若出现跨多步引用，由计划步骤声明依赖后再扩展，不在本次实现。

备选：继续传全部 evidence。这是当前重复 token 的主要来源，不采用。

### 4. 计划必须自包含执行意图

planner 提示词要求每一步 `purpose` 写出执行所需的业务字段（服务名、logger、异常类型、要拿到的信息），executor 依靠"计划 + 摘要"填参。这样 executor 不再需要 SOP 全文或完整告警。

备选：在计划里增加结构化的 `inputs` 字段。会扩大计划契约并引入新的参数绑定规则，本次先用用途文本承载，后续有需要再结构化。

### 5. 工具目录使用 JSON 并保留约束

`_catalog_payload` 改为 `json.dumps(..., ensure_ascii=False)`；`_visible_property` 的白名单增加 `minimum`、`maximum`、`minLength`、`maxLength`、`pattern`、`additionalProperties`、`examples`。服务端注入字段的过滤逻辑不变。

备选：继续使用 `repr`。模型虽能读懂，但不是标准协议，且测试无法可靠断言，因此不采用。

## Risks / Trade-offs

- **executor 缺少 SOP 细节** → 最小摘要保留 summary/rootCause；planner 的步骤用途必须写清业务字段，并加测试覆盖。
- **前序产出只传上一步可能不够** → SearchLog 的关键参数已服务端绑定；其他工具当前都是单步或紧邻依赖，先按最小规则落地，出现真实缺口再扩展。
- **摘要截断丢失关键信息** → 各字段有界但保留语义；测试断言关键字段存在。
- **工具目录变 JSON 后提示词格式变化** → 只改变序列化方式，不改变字段内容；加解析与约束保留测试。

## Migration Plan

无数据库、配置或 API 迁移；部署后端即可，回滚同样只需回退代码。

## Open Questions

（无）
