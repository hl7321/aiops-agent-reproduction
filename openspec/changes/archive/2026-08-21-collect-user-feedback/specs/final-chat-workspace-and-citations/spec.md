## ADDED Requirements

### Requirement: Chat 回答与引用接入持久反馈

Chat 工作区 SHALL 只为已经由服务器持久化的 assistant message 展示回答反馈；每条 citation SHALL 使用 assistant message id 作为 targetId、稳定 citation/chunk id 作为 subjectId。重新打开或切换会话时 SHALL 从反馈 API 恢复回答和各 citation 的反馈，且第二轮反馈不得继承第一轮目标。

#### Scenario: 完成后回答可反馈

- **WHEN** SSE complete 后历史对账返回持久 assistant message
- **THEN** 该回答显示 `UserFeedbackControl`
- **AND** 流式临时消息在获得真实 message id 前不提交反馈

#### Scenario: 单条 citation 独立恢复

- **WHEN** 一条 assistant message 包含多个引用且用户重新打开会话
- **THEN** 各 citation 按自身稳定 subjectId 恢复对应反馈
- **AND** 回答级反馈不与 citation 反馈混淆

#### Scenario: Chat 反馈失败保持可重试

- **WHEN** 回答或 citation 反馈提交失败
- **THEN** 用户输入保留且显示可访问错误
- **AND** 页面不乐观显示保存成功
