## 1. 共享合同与验收测试

- [x] 1.1 先为 SSE 公共 sequence、stream 请求、AgentToolCallAudit DTO/list data 和两个新 OpenAPI path 增加失败的 contracts/backend 合同测试
- [x] 1.2 扩展共享 Chat/SSE/OpenAPI 合同与导出，确保前端不复制私有 event union，并使 contracts typecheck/test 通过
- [x] 1.3 增加后端序列化与 OpenAPI 跨语言合同测试，覆盖 bearer、401/403、validation、审计父对象和共享 SSE response

## 2. 审计迁移与 Repository

- [x] 2.1 先增加 migration/metadata 测试，覆盖 `agent_tool_call_audits` 字段、索引、chat 外键、恰好一个父对象 CHECK 及禁止 parentCallId
- [x] 2.2 新增 Alembic revision、ORM model、不可变 record、Repository Protocol 与 owner-scoped SQLite adapter
- [x] 2.3 增加两个用户的 started/completed/failed/list 合同测试，验证稳定排序、跨 owner 不可见、脱敏错误和独立事务

## 3. Agent 工具与事件映射

- [x] 3.1 先为 TurnContext、单调 sequence、稳定 id、唯一 complete/error 终结和逐 Unicode 字符正文增加失败测试
- [x] 3.2 实现只转发真实 reasoning 的 AgentEventMapper，覆盖 tool started/delta/completed/failed、reference、共享 error 和非正文事件不拆分
- [x] 3.3 先测试并实现 tenant-bound `knowledge_retrieval` 与可注入 clock 的 `get_current_time` 工具工厂，证明不在 Agent 前固定检索
- [x] 3.4 实现 AgentToolAuditService 包装工具生命周期，并用日志捕获测试证明只记录参数键名、不记录 prompt/query/参数值/output/token/reasoning

## 4. Agent runner 与历史预算

- [x] 4.1 先测试 owner-scoped 历史转换、从最旧消息裁剪、P06 contextWindowTokens 预算和始终保留当前 user 消息
- [x] 4.2 实现可注入 token counter、model/tool/agent factory 的 AgentChatRunner，生产路径使用 LangChain 1.x `create_agent`
- [x] 4.3 使用 fake agent event stream 测试无工具、自主知识工具、当前时间、真实 reasoning、工具/provider 失败及两轮引用隔离，测试不得联网

## 5. 流式 Chat API 与持久化

- [x] 5.1 先增加 stream service/API 失败测试，覆盖调用模型前 owner 校验、user 先提交、assistant 成功后单次提交和失败无半消息
- [x] 5.2 扩展 Chat Repository/service/dependencies/router，提供 `POST /chat/sessions/{sessionId}/messages:stream` 并复用统一 request-id/安全错误
- [x] 5.3 完成 assistant 保存后逐 Unicode 字符发送正文与唯一 complete；tool/provider/持久化失败发送共享 error 且不生成假答案
- [x] 5.4 测试两轮 references/toolCallIds 隔离、reload 对应 metadata、多字节文本、客户端断开不删除已完成 assistant 和跨用户 403

## 6. 审计查询 API

- [x] 6.1 先增加 `GET /chat/sessions/{id}/tool-call-audits` API 失败测试，覆盖 envelope、稳定排序、401、父会话不存在/跨用户一致 403
- [x] 6.2 实现 owner-scoped audit dependency/router，先校验父会话再按 owner/session 查询，禁止从无 scope 查询推断资源存在

## 7. 前端 typed transport 与 Chat store

- [x] 7.1 先扩展 SSE/chat client 测试，覆盖 bearer/request-id、跨 chunk frame、共享 id/sequence 和 event union 类型收窄
- [x] 7.2 实现 typed chat stream client 和 store 的当前轮正文/reasoning/tool/reference/complete/error 状态，不提前实现完整 Chat 页面
- [x] 7.3 测试新轮引用清理、401/logout 受保护状态清理、服务端对账和禁止 localStorage 保存聊天领域/live 数据

## 8. 验证、真实 smoke 与归档

- [x] 8.1 运行 `uv run alembic upgrade head`、backend `uv run ruff check .`、`uv run pyright`、`uv run pytest`
- [x] 8.2 运行 contracts typecheck/test、frontend typecheck/test/build、`openspec validate --all` 与 `git diff --check`
- [x] 8.3 在 Qwen/Milvus 与 ignored 本机凭据可用时执行一次真实 Agent 对话 smoke；不可用时明确记录未执行，不把 fake 测试称为真实连通
- [x] 8.4 使用 `$openspec-verify-change` 检查完整性、正确性与设计一致性，修复全部 CRITICAL 并处理 WARNING 后重新运行受影响门禁
- [x] 8.5 将 delta specs 同步到主规格，确认任务与验证证据完整，再使用 `$openspec-archive-change` 归档
