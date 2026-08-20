## Context

P14 已提供 owner-scoped SQLite 会话/消息 Repository，P12 已提供绑定 `CurrentUser` 的 `knowledge_retrieval` Tool，P06 提供 Qwen Chat provider 与 context capability，P02 提供共享 SSE union。详见 `proposal.md` 的动机；本设计需要把这些边界组合成真实 Agent turn，同时保持 import-safety、tenant isolation 和失败时消息一致性。

## Goals / Non-Goals

**Goals:**

- 以 LangChain 1.x `create_agent` 作为唯一模型/工具循环，让模型自主选择知识检索或当前时间工具。
- 把 LangChain/LangGraph 运行事件集中映射为共享 SSE，并提供确定 sequence、Unicode 字符正文和唯一 complete。
- 明确 user、assistant 与 audit 的事务边界，失败时保留可解释状态且不产生半条 assistant。
- 建立可供 Chat 和后续 AIOps 复用的 owner-scoped 通用工具审计。
- 所有外部 client、clock、token counter 与 Agent factory 可注入，测试不读取真实配置或联网。

**Non-Goals:**

- 不接入 MCP 工具；P18 通过扩展 tool factory 接入。
- 不实现 durable Agent generation、HTTP Last-Event-ID、断线续传或跨系统原子事务。
- 不实现完整 Chat 产品页面，不保存隐藏思维链，不定义审计保留期策略。

## Decisions

### 1. 使用 create_agent 原生循环并设置单一事件适配层

生产路径由 P06 provider 创建 `ChatOpenAI`，再调用 LangChain 1.x `create_agent`。`AgentChatRunner` 负责一次 turn，`AgentEventMapper` 是框架事件到共享 SSE 的唯一适配点。这样模型可以真实自主调用工具，框架事件格式变化也只影响一个模块。

备选方案是手写 tool loop 或在最终答案后模拟工具事件；前者重复 Agent 框架职责，后者无法表达真实 started/completed/failed 时序，均不采用。

### 2. 每轮使用独立 TurnContext

`TurnContext` 保存 turnId、下一个 sequence、本轮 references、toolCallIds、正文 buffer 和终结状态。事件 id 为 `<turnId>:<sequence>`，sequence 从 1 单调增加；终结方法保证 error 与 complete 互斥、complete 最多一次。references/toolCallIds 不从上一轮初始化，reload 只读取每条 assistant 自身 metadata。

备选方案是在 session store 中复用可变引用集合；这会造成跨轮引用污染，违反 reload 语义，因此不采用。

### 3. assistant 先完整持久化，再发送正文字符

endpoint 先在 owner-scoped 事务中保存 user，然后加载/裁剪历史并执行 Agent。获得完整正文后，在一个事务内写入完整 assistant 及本轮 metadata；提交成功后才逐 Unicode 字符发送 `content.delta`，最后发送唯一 complete。Agent 或持久化失败保留 user 和已产生 audit，但不写 assistant。

这一顺序优先保证服务端历史永远完整。代价是客户端断线可能在数据库已有回答时没有收到 complete；P15 明确通过 reload 恢复，而不是虚构 durable replay。

### 4. 工具由可信 CurrentUser 在运行期绑定

tool factory 每轮创建 `knowledge_retrieval` 与 `get_current_time`。知识工具复用 P12 factory，并只接受不能表达 owner/tenant 的共享 input；任何 KB/document filter 均在当前 scope 内收窄。时间工具返回含时区 ISO 8601，并注入 clock 便于测试。

所有模型、Milvus 和数据库 client 只在 factory/dependency/显式调用创建；模块 import、测试收集和 OpenAPI 加载不联网。应用配置仍只来自本地 JSON 深合并，不读取 OS 环境变量。

### 5. 历史按模型 capability 确定性裁剪

每轮 user 提交后重新读取完整 owner-scoped 历史，使用可注入 token counter 和 P06 `contextWindowTokens` 预算，从最旧消息开始裁剪，同时为 system prompt、工具 schema 与输出预留容量并始终保留本轮 user。裁剪只改变模型输入，不删除 SQLite 数据。

备选方案是直接传入全历史或在 P15 建立摘要记忆；前者可能超过 context window，后者引入新的模型写入与一致性边界，因此不采用。

### 6. 审计使用独立短事务与排他父对象约束

Alembic 新增 `agent_tool_call_audits`，包含 owner、toolCallId、toolName、canonical arguments、`started|completed|failed`、有界 resultSummary、脱敏 errorMessage 和时间/duration。`chatSessionId` 与 `diagnosticTaskId` 通过 CHECK 恰好一个非空；现有 chat parent 使用外键，尚不存在的 diagnostic task 只保留规范化标量，不虚构外键，也不增加 parentCallId。

工具开始前创建 started，成功或失败后更新同一记录；每次写入使用独立短事务，使 Agent turn 失败仍保留生命周期。GET audit API 先 owner-scope 校验父会话，再按 owner/session 查询并稳定排序。

### 7. 审计数据与运行日志采用不同披露边界

完整 arguments 是仅 owner 可读的审计业务数据；resultSummary 有界且不等于完整工具输出。结构化运行日志只允许 requestId、owner/session、toolName/toolCallId、status、durationMs 和参数键名，禁止 prompt、query、参数值、完整 arguments、工具输出、token、正文和 reasoning。provider/API key 使用既有 redaction 替换为 `[redacted]`。

### 8. 前端只扩展 typed transport 与 UI-ready live state

前端复用公共 `sseClient` 的跨 chunk frame parser和共享 union，chat client 注入 bearer/request-id，store 维护当前轮正文、reasoning、tool lifecycle、references 和完成/错误状态。开始新轮及认证清理时清空 live state，聊天领域数据仍以服务端为事实来源且不写 localStorage。

## Risks / Trade-offs

- [LangChain 事件格式升级] → 只在 `AgentEventMapper` 解析框架 payload，并用 fake event fixtures 与合同测试锁定映射。
- [字符级 SSE 事件较多] → 这是明确验收合同；仅正文逐字符，其他事件保持原子，不在 P15 私自改为批量协议。
- [assistant 已保存但客户端未收到 complete] → reload 返回完整消息；将 durable turn replay/Last-Event-ID 留给独立 change。
- [审计 arguments 具有敏感性] → 强制 owner scope、API 父对象校验、日志禁止复制、错误脱敏；保留期后续单独设计。
- [全历史裁剪损失旧上下文] → 使用稳定预算与测试并保留 SQLite 全历史；摘要记忆不在本范围。
- [SQLite、模型、Milvus 无跨系统原子事务] → 使用明确消息/audit 状态与错误事件，不宣称不存在的原子保证。

## Migration Plan

1. 先发布共享 contracts 与 Alembic `agent_tool_call_audits` 迁移，并在临时 SQLite 验证 upgrade。
2. 发布 Repository、runner、tool factory、事件 mapper 与 API；旧的非流式 Chat operations 保持原语义。
3. 发布前端 typed stream transport/store 基础；完整页面由后续 change 消费。
4. 回滚应用代码时保留新增表不会影响 P14；需要数据库降级时执行该 revision 的 downgrade，只删除尚无其他功能依赖的审计表。
