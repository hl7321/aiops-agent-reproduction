## ADDED Requirements

### Requirement: AIOps 步骤与报告接入持久反馈

AIOps 工作区 SHALL 为真实持久化 diagnostic step 和 diagnostic report 分别展示 `UserFeedbackControl`，以 step id 或 report id 作为无 subject 的 target。重新打开诊断或从断流恢复持久状态时 SHALL 从反馈 API 恢复对应记录；timeline 中非 step 的 plan、tool event、evidence 或临时状态不得伪装成可反馈 step。

#### Scenario: 步骤和报告分别恢复

- **WHEN** 用户重新打开包含步骤和最终报告的诊断
- **THEN** 各 diagnostic step 恢复自己的反馈
- **AND** diagnostic report 恢复独立反馈

#### Scenario: 非目标 timeline 项不提供反馈

- **WHEN** timeline 展示 plan、tool lifecycle、evidence 或 task status
- **THEN** 这些项目不显示 diagnostic_step 反馈控件

#### Scenario: AIOps 反馈失败保持可重试

- **WHEN** step 或 report 的反馈更新/删除失败
- **THEN** UI 保持服务器已保存状态与本地待重试输入
- **AND** 不将 provider 或网络失败显示为成功
