# 聊天会话管理规格

## Purpose

本能力为后续流式 Agent 提供由服务端持久化、按当前用户隔离且可事务验证的聊天会话与消息生命周期，并确保前端刷新或重新认证后仍能从服务器恢复一致状态。

## Requirements

### Requirement: 聊天会话与消息由服务端持久化
系统 SHALL 将聊天会话与消息保存在服务端 SQLite 中，并把服务端数据作为会话列表、详情与消息历史的唯一事实来源。消息 MUST 包含稳定 id、会话 id、`user|assistant|system|tool` role、非空 content、会话内单调 sequence、createdAt 与结构化 metadata；metadata MUST 支持 toolCallIds 和完整 retrieval references。每条 reference MUST 保留 chunkId、documentId、knowledgeBaseId、source、excerpt、metadata、vectorRank/vectorScore、bm25Rank/bm25Score、rrfScore、rerankRank、rerankScore 与兼容 score；未命中分支使用 null，不能伪造 0 排名。

#### Scenario: 刷新后恢复会话
- **WHEN** 已认证用户创建会话并追加消息后重新读取会话详情
- **THEN** 系统从服务端返回已保存的会话和按 sequence 升序排列的消息，而不依赖浏览器本地领域缓存

#### Scenario: 保存结构化 metadata
- **WHEN** Agent 成功保存带完整 retrieval references 和 toolCallIds 的 assistant 消息
- **THEN** 再次读取详情时获得字段、nullable rank 和各阶段分数均一致的结构化 metadata

### Requirement: 所有聊天操作强制 owner scope
系统 SHALL 把当前认证 user id 同时作为 owner scope，并在会话及消息的读取、追加、清空和删除操作中显式限定 owner。受保护父会话不存在或属于其他用户时 MUST 返回相同的 `AUTH_FORBIDDEN` 403，且 MUST NOT 泄漏另一个用户的资源细节。

#### Scenario: 两个用户读取同一会话 id
- **WHEN** 用户 B 请求用户 A 的会话详情
- **THEN** 系统返回与父会话不存在相同的 `AUTH_FORBIDDEN` 403 envelope，且响应不包含用户 A 的会话或消息字段

#### Scenario: 两个用户修改同一会话 id
- **WHEN** 用户 B 尝试向用户 A 的会话追加消息、清空消息或删除会话
- **THEN** 每个操作均返回 `AUTH_FORBIDDEN` 403，并且用户 A 的数据保持不变

### Requirement: 会话创建、列表与详情具有确定性
系统 SHALL 支持创建空会话、按 `updatedAt DESC` 且以 id 作稳定次级排序列出当前 owner 的会话，以及读取包含有序消息的单个会话。新会话标题 MUST 为“新会话”。

#### Scenario: 创建空会话
- **WHEN** 已认证用户创建聊天会话
- **THEN** 系统返回标题为“新会话”、消息列表为空且归属于当前用户的新会话

#### Scenario: 更新时间相同的列表排序
- **WHEN** 两个会话具有相同 updatedAt
- **THEN** 列表仍使用稳定 id 次级排序返回确定顺序

### Requirement: 首条用户消息生成有界标题
系统 SHALL 对首条 user 消息的空白做规范化，并以最多 48 个 Unicode 字符生成会话标题。assistant、system 或 tool 消息 MUST NOT 生成标题，后续 user 消息 MUST NOT 覆盖已经生成的标题。

#### Scenario: 首条用户消息包含多余空白
- **WHEN** 新会话的首条 user 消息包含换行、制表或连续空格且规范化后超过 48 个字符
- **THEN** 标题由规范化文本的前 48 个 Unicode 字符生成

#### Scenario: 第一条消息不是用户消息
- **WHEN** 新会话先追加 assistant、system 或 tool 消息
- **THEN** 会话标题仍为“新会话”，直到首条 user 消息成功保存

#### Scenario: 后续用户消息不覆盖标题
- **WHEN** 已生成标题的会话再次追加 user 消息
- **THEN** 系统更新时间但保持原标题不变

### Requirement: 消息追加与会话更新原子一致
系统 SHALL 在同一事务边界内保存消息、分配会话内唯一递增 sequence，并更新会话 `updatedAt` 与必要的首条用户标题。任一步骤失败时 MUST 回滚该次追加的全部变更。

#### Scenario: 成功追加消息
- **WHEN** 当前 owner 向可见会话追加有效消息
- **THEN** 消息获得下一 sequence，且会话 updatedAt 与列表顺序同步更新

#### Scenario: 更新会话失败
- **WHEN** 消息插入后同一追加事务中的会话更新失败
- **THEN** 系统不保留该消息、sequence 或部分标题更新

### Requirement: 清空消息重置会话衍生状态
系统 SHALL 支持清空当前 owner 会话的全部消息、把标题重置为“新会话”并更新 `updatedAt`。清空后下一条消息的 sequence MUST 从 1 重新开始，下一条首个 user 消息 MUST 可重新生成标题。

#### Scenario: 清空已有会话
- **WHEN** 当前 owner 清空包含多条消息的会话
- **THEN** 详情返回空消息、标题“新会话”和更新后的 updatedAt，且会话本身仍存在

#### Scenario: 清空后重新对话
- **WHEN** 已清空会话追加新的首条 user 消息
- **THEN** 新消息 sequence 为 1，并由该消息重新生成标题

### Requirement: 删除会话同时删除子消息
系统 SHALL 支持当前 owner 删除会话，并同时删除该会话的全部子消息。成功响应 MUST 包含 `{deleted:true,sessionId}`；删除 MUST NOT 影响同一 owner 的其他会话或其他 owner 的任何数据。

#### Scenario: 删除包含消息的会话
- **WHEN** 当前 owner 删除包含消息的会话
- **THEN** 会话及其子消息不再可读取，响应包含被删除的 sessionId

### Requirement: 前端聊天状态与服务端对账
前端 SHALL 提供直接消费共享合同的 typed chat client 和可清理的受保护 chat store。store MUST 从服务端加载、创建、追加、清空和删除会话，并 MUST NOT 使用 localStorage 或静态数组作为聊天领域主存储；认证失效或 logout 时 MUST 清除内存中的受保护聊天状态。

#### Scenario: 登录后加载聊天状态
- **WHEN** 已认证前端加载会话列表并选择会话
- **THEN** store 通过公共 transport 携带 bearer 调用真实 API，并用成功 envelope 中的数据完成服务端对账

#### Scenario: 认证失效清理状态
- **WHEN** chat API 返回 401 或用户 logout
- **THEN** 前端清除当前会话、会话列表和消息等受保护内存状态，但不请求删除服务端业务数据

### Requirement: 本阶段不执行模型或流式 Agent
创建、读取、非流式追加、清空或删除操作 SHALL 仅管理会话与消息生命周期，MUST NOT 调用 LLM、Milvus、MCP 或启动 Agent。只有专用 `messages:stream` 操作 MAY 执行本 change 定义的 Agent；该执行 MUST NOT 使用临时进程内后台任务冒充 durable runtime。

#### Scenario: 通过非流式接口追加用户消息
- **WHEN** 用户通过非流式消息接口追加内容
- **THEN** 系统只持久化该消息和会话状态，不生成模型回复或 SSE 事件

#### Scenario: 通过专用流式接口追加用户消息
- **WHEN** 用户通过 `messages:stream` 提交内容
- **THEN** 系统按 Agent 流式规格执行本轮，而不改变其他会话操作的非模型语义

### Requirement: 流式 Agent 复用服务端会话生命周期
聊天会话 SHALL 在既有 owner-scoped 消息边界上支持流式 user turn。系统 MUST 在开始模型调用前持久化 user 消息，并仅在成功完成时保存一条完整 assistant 消息；assistant metadata MUST 保存且仅保存本轮 references 与 toolCallIds。

#### Scenario: 成功流式对话后读取详情
- **WHEN** owner 完成一轮流式 Agent 对话后重新读取会话详情
- **THEN** 服务端按 sequence 返回已保存 user 与完整 assistant 消息，assistant metadata 与本轮工具和引用一致

#### Scenario: 流式对话失败后读取详情
- **WHEN** user 消息保存后 Agent 执行失败
- **THEN** 详情保留 user 消息但不包含部分或空的 assistant 消息

### Requirement: 前端聊天状态支持当前流式轮次
前端 chat client/store SHALL 直接消费共享 stream 请求与 SSE union，维护当前轮正文、真实 reasoning、工具状态、references、完成或错误状态。开始新一轮、认证失效或 logout MUST 清除对应内存 live state，且 MUST NOT 写入 localStorage。

#### Scenario: 第二轮开始
- **WHEN** 第一轮存在引用且用户开始第二轮
- **THEN** store 清空上一轮 live references/tool 状态，并只累计第二轮事件

#### Scenario: 流式请求认证失效
- **WHEN** stream 请求返回认证失效
- **THEN** 前端执行统一受保护状态清理，不请求删除服务端聊天数据

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
