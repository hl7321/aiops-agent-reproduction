## MODIFIED Requirements

### Requirement: 每轮引用与历史上下文相互隔离
系统 SHALL 为每轮创建新的 references 与 toolCallIds 集合，并在 reload 时只从对应 assistant message metadata 恢复。模型历史 MUST 由当前会话的可用摘要与压缩高水位之后的消息装配，MUST NOT 删除、改写服务端完整历史或回退为无摘要的最旧消息裁剪；当前候选 user 消息 MUST 只在 95% 安全检查通过后保存并进入本轮模型输入。

#### Scenario: 连续两轮仅第一轮检索
- **WHEN** 第一轮产生知识引用而第二轮未调用知识工具
- **THEN** 第二轮 live state 与 assistant metadata 不包含第一轮引用或 toolCallIds

#### Scenario: 历史超过上下文预算
- **WHEN** 会话存在历史摘要与压缩消息高水位
- **THEN** 模型输入包含该会话摘要和高水位之后的消息，不重复发送已摘要逐条历史，SQLite 完整历史保持不变

#### Scenario: 候选轮次达到硬上限
- **WHEN** 当前模式完成允许的自动压缩后，包含候选 user 消息的预算达到模型窗口 95%
- **THEN** 系统返回共享上下文上限错误，且不保存候选 user 消息、不调用模型或工具

## ADDED Requirements

### Requirement: 流式错误复用上下文上限目录
流式聊天 SHALL 对 `CHAT_CONTEXT_LIMIT_REACHED` 使用与 HTTP failure envelope 相同的错误定义。响应尚未开始时 MUST 返回 HTTP 409；响应已经开始时 MUST 发送共享 SSE `error` 形状，且两者不能具有冲突的 category、status 或默认消息。

#### Scenario: 流开始前预算拒绝
- **WHEN** 候选预算在创建 StreamingResponse 前达到 95%
- **THEN** 客户端收到 409 failure envelope 而不是伪装成成功的空 SSE 流
