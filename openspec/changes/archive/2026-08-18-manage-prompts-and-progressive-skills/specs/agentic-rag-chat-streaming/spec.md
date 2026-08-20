## MODIFIED Requirements

### Requirement: 模型自主选择受 tenant 约束的工具
系统 SHALL 使用 LangChain 1.x `create_agent` 让模型自主决定是否调用工具，初始工具集 MUST 至少包含 `knowledge_retrieval`、`get_current_time` 与当前请求 owner-scoped 的 `load_skill`。系统 MUST NOT 在 Agent 前无条件检索知识库或加载 Skill 正文；知识工具 MUST 绑定当前用户，模型提供的过滤条件只能收窄、不能扩大 owner/tenant 权限；`load_skill` MUST 只能读取本轮选中的当前 owner Skill。每轮 system prompt MUST 先保留不可覆盖的平台安全规则，再装配当前用户 Prompt 与仅含 name/description 的选中 Skill catalog。reasoning 仍只能来自模型真实事件。

#### Scenario: 模型无需知识工具
- **WHEN** 模型判断当前问题无需知识检索
- **THEN** 系统生成回答且不调用 `knowledge_retrieval`、不发送虚假的工具或引用事件

#### Scenario: 模型自主检索知识
- **WHEN** 模型选择调用 `knowledge_retrieval`
- **THEN** 工具始终使用当前用户 scope，并只返回该 scope 内允许知识库的结果

#### Scenario: 模型调用当前时间工具
- **WHEN** 模型选择调用 `get_current_time`
- **THEN** 工具返回带明确时区的 ISO 8601 当前时间

#### Scenario: 模型按需调用 Skill
- **WHEN** 模型根据摘要判断需要本轮已选 Skill
- **THEN** 模型调用 `load_skill` 后才取得正文，工具仍强制当前 owner 与选择白名单

#### Scenario: 用户配置不能覆盖平台边界
- **WHEN** 当前用户 Prompt 或 Skill 正文要求跨 tenant 访问或替换可信工具规则
- **THEN** Agent 的 CurrentUser、Repository scope 与工具实现保持不变，越权内容不能生效

#### Scenario: reasoning 保持真实来源
- **WHEN** 动态 Prompt/Skill 装配完成且模型未提供 reasoning event
- **THEN** 系统不合成、不推断也不发送 reasoning
