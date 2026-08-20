## MODIFIED Requirements

### Requirement: 聊天会话与消息由服务端持久化
系统 SHALL 将聊天会话与消息保存在服务端 SQLite 中，并把服务端数据作为会话列表、详情与消息历史的唯一事实来源。消息 MUST 包含稳定 id、会话 id、`user|assistant|system|tool` role、非空 content、会话内单调 sequence、createdAt 与结构化 metadata；metadata MUST 支持 toolCallIds 和完整 retrieval references。每条 reference MUST 保留 chunkId、documentId、knowledgeBaseId、source、excerpt、metadata、vectorRank/vectorScore、bm25Rank/bm25Score、rrfScore、rerankRank、rerankScore 与兼容 score；未命中分支使用 null，不能伪造 0 排名。

#### Scenario: 刷新后恢复会话
- **WHEN** 已认证用户创建会话并追加消息后重新读取会话详情
- **THEN** 系统从服务端返回已保存的会话和按 sequence 升序排列的消息，而不依赖浏览器本地领域缓存

#### Scenario: 保存结构化 metadata
- **WHEN** Agent 成功保存带完整 retrieval references 和 toolCallIds 的 assistant 消息
- **THEN** 再次读取详情时获得字段、nullable rank 和各阶段分数均一致的结构化 metadata
