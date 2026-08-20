## MODIFIED Requirements

### Requirement: 每轮引用与历史上下文相互隔离
系统 SHALL 为每轮创建新的完整 retrieval citations 与 toolCallIds 集合，并在 reload 时只从对应 assistant message metadata 恢复。实时 `reference.source` 与成功 assistant metadata MUST 对同一 citation 保留 chunk/document/knowledgeBase id、source/excerpt/metadata 和 vector/BM25/RRF/rerank 的原始 rank/score；nullable 分支命中语义不得改写。模型历史 MUST 由当前会话的可用摘要与压缩高水位之后的消息装配，MUST NOT 删除、改写服务端完整历史或回退为无摘要的最旧消息裁剪；当前候选 user 消息 MUST 只在 95% 安全检查通过后保存并进入本轮模型输入。

#### Scenario: 连续两轮仅第一轮检索
- **WHEN** 第一轮产生知识引用而第二轮未调用知识工具
- **THEN** 第二轮 live state 与 assistant metadata 不包含第一轮引用或 toolCallIds，第一轮 metadata 仍保留自身完整 citation

#### Scenario: 实时引用与 reload 一致
- **WHEN** 本轮 knowledge_retrieval 返回包含单分支 null rank 的 citation 并成功完成
- **THEN** 实时 reference.source 与 reload 后对应 assistant metadata 的字段、null 和各阶段原始分数一致

#### Scenario: 历史超过上下文预算
- **WHEN** 会话存在历史摘要与压缩消息高水位
- **THEN** 模型输入包含该会话摘要和高水位之后的消息，不重复发送已摘要逐条历史，SQLite 完整历史保持不变

#### Scenario: 候选轮次达到硬上限
- **WHEN** 当前模式完成允许的自动压缩后，包含候选 user 消息的预算达到模型窗口 95%
- **THEN** 系统返回共享上下文上限错误，且不保存候选 user 消息、不调用模型或工具
