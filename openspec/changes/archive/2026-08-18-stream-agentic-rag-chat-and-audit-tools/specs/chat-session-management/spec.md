## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: 本阶段不执行模型或流式 Agent
创建、读取、非流式追加、清空或删除操作 SHALL 仅管理会话与消息生命周期，MUST NOT 调用 LLM、Milvus、MCP 或启动 Agent。只有专用 `messages:stream` 操作 MAY 执行本 change 定义的 Agent；该执行 MUST NOT 使用临时进程内后台任务冒充 durable runtime。

#### Scenario: 通过非流式接口追加用户消息
- **WHEN** 用户通过既有非流式消息接口追加内容
- **THEN** 系统只持久化该消息和会话状态，不生成模型回复或 SSE 事件

#### Scenario: 通过专用流式接口追加用户消息
- **WHEN** 用户通过 `messages:stream` 提交内容
- **THEN** 系统按 Agent 流式规格执行本轮，而不改变其他会话操作的非模型语义
