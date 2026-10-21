# Spec Delta

## MODIFIED Requirements

### Requirement: Executor 只接收执行所需的最小上下文

Executor 的填参调用 SHALL 只包含：当前工具说明、整份计划（工具与用途）、最小告警摘要、当前步骤真正需要的前序产出、上一次错误。MUST NOT 包含完整告警原文中的 `rawContext`/`fingerprint`/`receivers` 等诊断无关字段，MUST NOT 包含与当前步骤无关的全部证据。Planner 仍 SHALL 获得完整告警、SOP 与规范化后的可选用户 query；Report 仍 SHALL 获得全部已持久化证据。

Planner 的上下文 MUST 以独立标签区分 `用户问题`、告警、SOP 与工具目录，MUST NOT 只在 SOP 或告警中偶然出现 query 信息时才让 Planner 获知用户目标。Executor MUST NOT 因本要求获得整段对话历史或全部证据；Planner 的步骤用途 SHALL 保留执行该步骤所需的 query 关键目标，Executor 通过最小计划与当前步骤所需前序产出完成执行。

#### Scenario: executor 上下文不含完整告警原文

- **WHEN** executor 为任意计划步骤生成参数
- **THEN** 提示词中不出现 `rawContext`、`fingerprint`、`receivers` 等字段，只保留服务、告警名、incident/trace 标识、告警时间与有界摘要

#### Scenario: executor 只拿当前步骤需要的前序产出

- **WHEN** 当前步骤需要前面步骤的产出
- **THEN** 只传入该步骤需要的最近一条产出（有界长度），不传入全部 evidence 列表

#### Scenario: SearchLog 步骤不重复全部证据

- **WHEN** 当前步骤是 SearchLog，且 Query/From/To/Region/TopicId 已由服务端绑定
- **THEN** executor 上下文不重复塞入知识库全文与其他无关证据

#### Scenario: planner 上下文保持完整

- **WHEN** planner 排计划
- **THEN** 它仍能看到完整告警、SOP、规范化后的可选用户 query 与完整工具目录

#### Scenario: 纯 query 在 planner 上下文中独立可见

- **WHEN** 本轮 query 非空且 alerts 为空，知识检索返回与 query 无关或没有任何 SOP
- **THEN** planner 提示词仍包含明确的 `用户问题` 与原始 query，不把空告警和空 SOP 当成没有诊断目标

#### Scenario: executor 不继承完整对话上下文

- **WHEN** planner 已看到 query、告警、SOP 与工具目录并生成计划
- **THEN** executor 只收到该计划、当前工具说明、最小告警摘要与当前步骤必要的前序产出，不收到完整 SOP 全文、全部证据或对话历史
