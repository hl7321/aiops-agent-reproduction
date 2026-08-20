## ADDED Requirements

### Requirement: 聊天会话持久化记忆派生状态
聊天会话 SHALL 在既有标题和时间戳之外持久化记忆模式、nullable 摘要、已压缩消息高水位、最近 context token 投影和 nullable 最后压缩时间。清空消息 MUST 同时把这些派生状态重置为默认模式以外的初始空状态；完整消息未被清空时，压缩操作 MUST NOT 删除或改写消息。

#### Scenario: 清空已压缩会话
- **WHEN** 当前 owner 清空一个已有摘要和压缩高水位的会话
- **THEN** 消息为空、标题恢复“新会话”，摘要为空、高水位与 contextTokens 为 0、lastCompactedAt 为空，memoryMode 保持用户当前选择

#### Scenario: 压缩后读取详情
- **WHEN** 会话完成一次记忆压缩后重新读取详情
- **THEN** session DTO 返回持久化记忆状态且 messages 仍包含全部原始历史

### Requirement: 会话记忆写操作复用 owner-scoped Repository 边界
Repository 的记忆模式更新、摘要条件写回和 token 投影更新方法 MUST 显式以 `owner_user_id` 为第一个业务参数，并在同一数据库语句中限定 owner 与 session id。领域服务 MUST 只接收不可变 record，不能接收 ORM model 或裸数据库 session。

#### Scenario: 参数级 owner scope
- **WHEN** Repository 合同测试构造缺少 owner_user_id 的记忆写调用
- **THEN** 调用在参数边界失败，不能形成无 owner 的宽更新
