# Agentic RAG 流式聊天与工具审计设计

## 目标与范围

P15 在 P14 持久会话之上建立真实的多轮流式 Agent。LangChain 1.x `create_agent` 负责模型与工具循环，模型自主决定是否调用 `knowledge_retrieval` 或 `get_current_time`；系统禁止在 Agent 运行前固定执行 RAG。P15 不接入 MCP、不实现 durable 聊天生成任务，也不完成 Chat 产品页面。

## 方案选择

采用 `create_agent` 原生工具循环与独立事件映射层。备选的手写工具循环会重复 LangChain Agent 职责；运行结束后模拟工具事件无法表达真实 started/completed/failed 时序，因此均不采用。

整体调用链为：

```text
FastAPI stream endpoint
  -> owner/session validation
  -> persist user message
  -> load and trim session history
  -> AgentChatRunner(create_agent)
       -> tenant-scoped knowledge_retrieval
       -> get_current_time
       -> AgentEventMapper -> shared SSE
       -> AgentToolAuditService -> SQLite audit
  -> persist complete assistant message
  -> Unicode content.delta stream
  -> complete once
```

## 组件边界

### AgentChatRunner

`AgentChatRunner` 表达一次 Agent turn。它接收可信 `CurrentUser`、session id、裁剪后的历史、注入的 chat model、工具工厂、事件 sink 和持久化边界；它不接收全局 tenant，也不直接构造 FastAPI response。

生产 factory 使用 P06 的 `QwenOpenAIProvider` 创建 `ChatOpenAI`，再调用 LangChain 1.x `create_agent`。测试注入可控 fake model/event source，不读取本机凭据、不联网。模块 import 不创建模型、Milvus 或数据库 client。

### AgentEventMapper

`AgentEventMapper` 是 LangChain/LangGraph 运行事件与共享 SSE union 之间的唯一适配层。框架事件字段变化只影响该层，不允许 router、store 或 audit repository 直接解析私有框架 payload。

Mapper 只转发模型真实提供的 reasoning；普通 content、tool input、日志或模板文本不能生成 reasoning。最终回答先完整收集，之后由后端按 Python Unicode 字符逐个生成 `content.delta`。tool、reasoning、reference、complete 和 error 事件不按字符拆分。

### TurnContext

每轮创建新的 `TurnContext`，持有 `turn_id`、下一个 sequence、本轮 reference 去重表、toolCallIds 和最终正文 buffer。事件 id 固定为 `<turnId>:<sequence>`，sequence 从 1 单调增加。`complete` 由单一终结方法生成并强制最多一次；error 路径不能再发送 complete。

references 和 toolCallIds 不从上一轮 assistant metadata 初始化。reload 时每条 assistant 只读取自身 metadata，因此第二轮不会继承第一轮 live references。

### 工具工厂

工具列表至少包含：

- `knowledge_retrieval`：复用 P12 tool factory，在创建时绑定可信 `CurrentUser` 和 retrieval service。模型 input 不包含 owner/tenant，filter 不能扩大当前用户权限。
- `get_current_time`：返回显式时区的当前 ISO 8601 时间；时钟通过依赖注入，测试不依赖系统当前时间。

P15 不添加 MCP tool。P18 只需扩展 tool factory，不修改消息、SSE 或 audit 主边界。

## 多轮历史与上下文预算

每轮在 user message 成功提交后重新读取当前 owner/session 的全部消息，转换为 LangChain messages。使用 chat model/token-counter 边界和 P06 `modelCapabilities.contextWindowTokens` 计算预算，并为 system prompt、工具 schema 与输出预留容量。从最旧消息开始裁剪，始终保留本轮 user message；裁剪只影响模型输入，不删除 SQLite 历史。

token counter 可注入，自动化测试使用确定性 fake counter。缺少可用 capability profile 或无法在预算内保留本轮消息时返回安全 SSE error，不静默丢弃当前输入。

## SSE 合同与时序

`POST /chat/sessions/{sessionId}/messages:stream` 使用 bearer、统一 request id 和共享错误结构。请求 body 复用 user content/metadata 语义，但 role 由 endpoint 固定为 user，客户端不能借流式接口写 assistant/tool。

共享 SSE 基类增加必填非负 `sequence`，所有事件仍包含 `id`、`type`、`channel=chat` 和 `timestamp`。典型成功时序为：

1. 可选真实 `reasoning.delta`。
2. 零到多个 `tool.call started`。
3. 对应的 `tool.call completed` 或 `failed`。
4. knowledge tool 的零到多个 `reference.source`。
5. 完整 assistant 成功持久化。
6. 最终正文逐 Unicode 字符的 `content.delta`。
7. 唯一 `complete`，finishReason 为 `stop`。

模型不调用工具时直接进入正文和 complete，不产生 knowledge tool 或引用事件。provider/tool/持久化失败发送相应 `tool.call failed`（如果工具已开始）和一个共享 `error`，不生成假答案、不发送 complete。

前端 `sseClient` 继续处理跨 chunk frame；P15 增加 typed `chatStreamClient` 和 chat store 的本轮 live events/references/tool 状态。它不复制 SSE union，不把消息或 live state写入 localStorage。

## 消息持久化与事务

流开始前先在独立事务中校验 owner/session 并保存 user message；验证与写入不能分成可被越权竞态利用的无 scope 查询。随后重新加载历史，确保 Agent 输入包含刚保存的 user message。

Agent 成功返回完整最终正文后，assistant message 在一个事务中一次性写入，metadata 只保存本轮 references/toolCallIds。assistant 保存成功后才发送正文字符和 complete；保存失败只发送 error。

Agent、provider 或 tool 失败保留 user message 和已产生的 audit，但不写 assistant。浏览器在 assistant 已完整保存后断开时，数据库保留完整 assistant；系统永远不保存部分正文。网络、SQLite、模型和 Milvus 之间不宣称跨系统原子事务。

## 通用工具调用审计

Alembic 新增 `agent_tool_call_audits`：

- `id`、`owner_user_id`、稳定 `tool_call_id`。
- `chat_session_id`、`diagnostic_task_id` 二选一，CHECK 保证恰好一个非空。
- `tool_name`、Canonical JSON `arguments`。
- `status`：`started|completed|failed`。
- `result_summary`、脱敏 `error_message`。
- `started_at`、`completed_at`、`duration_ms`。

当前存在的 `chat_session_id` 使用真实外键和级联删除；P15 尚无 diagnostic task 表，因此 `diagnostic_task_id` 保留规范化标量与排他约束，不虚构不存在的外键，也不增加 `parentCallId`。

工具开始前创建 started audit；成功或失败后更新同一记录。每次审计写入使用独立短事务，以便 Agent turn 失败时仍保留生命周期。`GET /chat/sessions/{id}/tool-call-audits` 先按 owner scope 校验父会话，再按 owner/session 查询并按 startedAt、id 稳定排序。不存在和跨 owner 父会话复用 P14 的 `AUTH_FORBIDDEN` 403。

arguments 是 owner-scoped 业务审计数据，可保存完整结构化工具输入；API 只向同一 owner 返回。`result_summary` 必须有界且不等于完整 tool output，`error_message` 使用现有 secret redaction。结构化运行日志只能记录 requestId、owner/session、toolName、toolCallId、status、durationMs 和参数键名，禁止 prompt、query、参数值、完整 arguments、tool output、token、消息正文和模型 reasoning。

## 错误与安全

- session 必须在调用模型前完成 owner 校验，模型不能通过参数改变 owner/tenant。
- knowledge filter 仍受 P05/P12 tenant scope 收缩，空 KB 结果不连接 Milvus。
- 工具异常转换为共享安全错误；原始 provider exception、API key、query、args 和 output 不进入 SSE 或日志。
- 只有模型真实事件携带 reasoning 时才发送 `reasoning.delta`，禁止合成或回放隐藏思维链。
- audit 参数只在 owner-scoped Repository/API 中可见，所有 list/get 方法显式接收 owner_user_id。
- import、测试收集和 OpenAPI 加载不得连接外部服务。

## 测试策略

自动化测试先使用 fake model、fake Agent event stream、fake retrieval 和 fake clock，覆盖：

- 模型不调用 knowledge tool 与模型自主调用两条路径。
- reasoning 存在/不存在、工具 started/completed/failed、引用和共享 error。
- 严格 sequence、稳定 id、complete 仅一次、中文/emoji 等多字节 Unicode 字符拆分。
- user 先持久化、assistant 成功后单次持久化、失败无 assistant 半消息。
- 两轮 references/toolCallIds 隔离及 reload 对应 metadata。
- 历史 owner scope、上下文裁剪和本轮 user 永远保留。
- audit started/completed/failed、排他 parent、duration、参数 JSON、结果摘要、跨用户 403。
- 日志 capture 证明 prompt/query/参数值/output/token sentinel 不出现，仅参数键可见。
- contracts/OpenAPI、SSE parser 跨网络 chunk、前端 typed transport/live state/401 cleanup。

最终运行 migration、backend Ruff/strict Pyright/pytest、contracts typecheck/test、frontend typecheck/test/build、`openspec validate --all` 与 `git diff --check`。本机 Qwen/Milvus 凭据和服务可用时执行一次真实对话 smoke；不可用时明确记录未执行，不把 fake 测试称为真实连通。

## 风险与取舍

- LangChain 事件格式可能变化：集中在 mapper 适配并用 fixture 合同测试保护。
- 字符级 SSE 事件数量较多：这是明确合同要求；不对非正文事件做拆分，也不在 P15 引入批量字符协议。
- assistant 在发送正文前已保存：客户端断开后 reload 可恢复完整消息，但客户端可能没有收到 complete；P15 不实现 Last-Event-ID 或 durable turn replay。
- audit 保存完整 arguments 会增加敏感性：严格 owner scope、禁止日志复制、结果只保存有界 summary；未来保留期策略由独立 change 定义。
- 全历史裁剪会丢失最旧模型上下文但不删除数据：使用确定性预算和测试，摘要记忆不在 P15 范围。
