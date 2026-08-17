# 聊天会话管理规格

## Purpose

本能力为后续流式 Agent 提供由服务端持久化、按当前用户隔离且可事务验证的聊天会话与消息生命周期，并确保前端刷新或重新认证后仍能从服务器恢复一致状态。

## Requirements

### Requirement: 聊天会话与消息由服务端持久化
系统 SHALL 将聊天会话与消息保存在服务端 SQLite 中，并把服务端数据作为会话列表、详情与消息历史的唯一事实来源。消息 MUST 包含稳定 id、会话 id、`user|assistant|system|tool` role、非空 content、会话内单调 sequence、createdAt 与结构化 metadata；metadata MUST 支持 references 和 toolCallIds。

#### Scenario: 刷新后恢复会话
- **WHEN** 已认证用户创建会话并追加消息后重新读取会话详情
- **THEN** 系统从服务端返回已保存的会话和按 sequence 升序排列的消息，而不依赖浏览器本地领域缓存

#### Scenario: 保存结构化 metadata
- **WHEN** 调用方追加带 references 和 toolCallIds 的消息
- **THEN** 再次读取详情时获得字段和值均一致的结构化 metadata

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
本能力 SHALL 仅管理会话与消息生命周期。创建、读取、追加、清空或删除操作 MUST NOT 调用 LLM、Milvus、MCP，且 MUST NOT 用临时进程内任务替代后续流式 Agent。

#### Scenario: 追加用户消息
- **WHEN** 用户通过非流式消息接口追加内容
- **THEN** 系统只持久化该消息和会话状态，不生成模型回复或 SSE 事件
