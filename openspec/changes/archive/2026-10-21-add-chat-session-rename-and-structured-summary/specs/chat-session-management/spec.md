# Spec Delta

## ADDED Requirements

### Requirement: 会话标题可显式重命名

系统 SHALL 支持通过 `PATCH /chat/sessions/{id}` 显式重命名当前 owner 的会话。标题 MUST 经空白规范化后为 1..128 个 Unicode 字符；空白或超长 MUST 返回共享 validation 错误。更新 MUST 只影响目标会话并刷新 `updatedAt`。显式重命名后，后续首条或后续 user 消息 MUST NOT 覆盖该标题；只有标题仍为默认"新会话"时，首条 user 消息才自动生成标题。

#### Scenario: 成功重命名

- **WHEN** 当前 owner 对已有会话提交合法新标题
- **THEN** 会话标题被更新、updatedAt 刷新，列表与详情返回新标题

#### Scenario: 标题非法

- **WHEN** 标题为空白或超过 128 个字符
- **THEN** 返回 `VALIDATION_REQUEST_INVALID`，原标题保持不变

#### Scenario: 跨用户重命名

- **WHEN** 用户 B 尝试重命名用户 A 的会话
- **THEN** 返回与父会话不存在一致的 `AUTH_FORBIDDEN` 403，且用户 A 的标题不变

#### Scenario: 重命名后首条消息不覆盖

- **WHEN** 用户先把"新会话"重命名为自定义标题，再发送首条 user 消息
- **THEN** 标题保持自定义值，不被自动标题覆盖
