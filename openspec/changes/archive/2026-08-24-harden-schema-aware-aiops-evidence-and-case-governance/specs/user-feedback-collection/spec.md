## ADDED Requirements

### Requirement: 报告反馈可作为 owner-scoped 知识提升审批
当前 owner 对 `diagnostic_report` 的最新持久反馈 SHALL 作为报告提升资格的一部分：只有 `positive` 才表示认可，`negative`、不存在或已删除反馈均不构成认可。提升服务 MUST 重新读取真实 report 与 feedback 并在同一 owner scope 验证，不得相信客户端提交的认可布尔值；反馈本身仍只表达用户评价，提交 positive 不得自动产生外部写入。

#### Scenario: positive feedback 后显式提升
- **WHEN** owner 保存 positive diagnostic_report feedback，随后单独调用报告提升操作
- **THEN** 服务端重新验证反馈和报告资格，再决定创建或关联 canonical case

#### Scenario: 修改或删除认可
- **WHEN** owner 在提升前把 positive 改为 negative 或删除反馈
- **THEN** 后续提升不再满足审批条件，且反馈操作本身不创建或删除既有知识资产

#### Scenario: 客户端伪造认可
- **WHEN** 客户端请求提升但没有同 owner 的真实 positive feedback
- **THEN** 服务端拒绝提升，不接受请求正文中的任意 approval/owner 字段替代持久反馈
