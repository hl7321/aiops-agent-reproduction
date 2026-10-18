# Spec Delta

## ADDED Requirements

### Requirement: Executor 只接收执行所需的最小上下文

Executor 的填参调用 SHALL 只包含：当前工具说明、整份计划（工具与用途）、最小告警摘要、当前步骤真正需要的前序产出、上一次错误。MUST NOT 包含完整告警原文中的 `rawContext`/`fingerprint`/`receivers` 等诊断无关字段，MUST NOT 包含与当前步骤无关的全部证据。Planner 仍 SHALL 获得完整告警与 SOP；Report 仍 SHALL 获得全部已持久化证据。

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
- **THEN** 它仍能看到完整告警、SOP 与完整工具目录

### Requirement: 模型可见工具说明使用标准 JSON 并保留官方约束

模型可见的工具目录 SHALL 是合法 JSON 文本，MUST NOT 使用 Python `repr` 输出。字段投影 MUST 保留官方 schema 中的 `minimum`、`maximum`、`minLength`、`maxLength`、`pattern`、`additionalProperties` 等约束；服务端注入字段仍 MUST NOT 出现在模型可见说明与必填列表中。

#### Scenario: 工具目录可被 JSON 解析

- **WHEN** 系统把工具目录写入 planner 或 executor 的提示词
- **THEN** 该段文本可以被标准 JSON 解析器解析，不出现单引号字符串、`None` 或 `True`

#### Scenario: 官方范围约束被保留

- **WHEN** 官方工具 schema 为某个字段声明了 `minimum`、`maximum`、`pattern` 或 `additionalProperties`
- **THEN** 模型可见说明保留这些约束

#### Scenario: 服务端字段仍然隐藏

- **WHEN** 工具参数由服务端注入（例如 SearchLog 的 Region/TopicId/From/To）
- **THEN** 这些字段不出现在模型可见说明与必填列表中
