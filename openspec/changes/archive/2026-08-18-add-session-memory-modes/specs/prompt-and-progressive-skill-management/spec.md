## MODIFIED Requirements

### Requirement: system prompt 只装配可信规则、当前 Prompt 与 Skill 摘要
每轮 Chat Agent 请求 SHALL 在同一个 owner-scoped 请求快照中按平台安全规则、当前用户 Prompt、选中 Skill catalog、当前会话历史摘要与未压缩消息的顺序装配上下文并计算候选预算。Skill catalog MUST 只包含选中 Skill 的 name 与 description，MUST NOT 包含完整正文。用户 Prompt MUST 被视为低于平台规则的用户偏好，不能扩大 tenant scope、替换可信工具实现或绕过安全与记忆硬上限。

#### Scenario: 选中 Prompt 与两个 Skill
- **WHEN** 用户选择一个 Prompt 和两个 Skill 后发起新一轮对话
- **THEN** 本轮 system prompt 包含平台规则、该 Prompt 与两个 name/description，且不包含任一 Skill 正文

#### Scenario: 用户 Prompt 请求绕过安全规则
- **WHEN** 当前 Prompt 声称允许跨用户访问、要求忽略平台工具边界或跳过上下文硬上限
- **THEN** Agent 的 CurrentUser、Repository/Tool scope 与 95% 预算保护保持不变，越权内容不能生效

#### Scenario: 配置在轮次之间变化
- **WHEN** 用户在两轮之间更新 Prompt 或 Skill 选择
- **THEN** 下一轮使用新配置刷新 token 投影并装配上下文，而已经开始的轮次不因中途变化扩大允许 Skill 集合

#### Scenario: 已压缩会话装配配置
- **WHEN** 会话已有摘要且仍有未压缩消息
- **THEN** 同一轮预算和模型输入同时包含当前 Prompt/Skill 摘要、会话摘要与未压缩消息，不重复注入已压缩逐条历史
