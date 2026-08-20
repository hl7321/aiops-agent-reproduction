## 1. 合同与失败测试

- [x] 1.1 先为共享错误目录、Chat memory mode/session DTO、更新请求和两条 OpenAPI operation 编写 contracts 失败测试，再更新 TypeScript contracts 与机器可读 manifest
- [x] 1.2 先为后端 Pydantic 合同、FastAPI OpenAPI、HTTP/SSE 错误复用和 `SYSTEM_MODEL_CAPABILITY_MISSING` 编写失败测试
- [x] 1.3 先为前端 chatClient/store 的读取、更新、compact、401 清理和服务端对账编写失败测试

## 2. 数据库迁移与 Repository 边界

- [x] 2.1 新增 Alembic `20260818_0009`，为 `chat_sessions` 添加三模式约束、摘要、高水位、context token 与最后压缩时间，并覆盖 upgrade/downgrade/fresh database/metadata 一致性
- [x] 2.2 扩展 Chat ORM 与不可变 records，保持默认状态、非负约束和 UTC 时间语义
- [x] 2.3 先写 Repository contract 与两个用户测试，再实现 owner-scoped 模式更新、token 投影、压缩条件写回和批量详情读取；所有写操作首个业务参数为 owner_user_id
- [x] 2.4 更新 clear 事务使其保留 memory mode 但重置摘要、高水位、token 与时间，并验证失败回滚和完整消息不被压缩操作修改

## 3. Token 预算与摘要服务

- [x] 3.1 先写纯函数测试，再实现内部调用 LangChain `count_tokens_approximately` 的 `estimate_context_tokens`，支持注入 estimator 并拒绝负结果
- [x] 3.2 实现可注入 model capability provider，缺失当前 chat model profile 时在创建 client 前返回安全明确错误
- [x] 3.3 先写完整 turn 边界与 `canCompact` 测试，再实现从高水位后选择可压缩 user/assistant 配对和装配摘要/未压缩消息的纯逻辑
- [x] 3.4 先写 fake LLM 测试，再实现摘要器，覆盖旧摘要增量、非空输出、安全日志、失败零写入与过期高水位条件写回
- [x] 3.5 实现 memory projector，按当前 Prompt/Skill snapshot 刷新 contextTokens、contextWindowTokens、contextUsagePercent 与 canCompact

## 4. 三模式策略与流式保护

- [x] 4.1 先写确定 estimator 测试覆盖 `every_30_turns` 的 29/30 turn、`context_70_percent` 的 69/70% 和 manual 不自动压缩
- [x] 4.2 实现请求级 memory coordinator，在同一配置 snapshot 上判断自动压缩、重新估算并保证不同会话与 owner 隔离
- [x] 4.3 重构 P15 stream prepare，使候选 user 消息只在 95% 检查通过后事务性写入，并用摘要 + 未压缩消息替换旧 `trim_chat_history` 生产路径
- [x] 4.4 固定 prepare 阶段的 Prompt/Skill/memory snapshot 供 Agent runner 使用，保证预算输入与实际模型输入一致且 Skill 正文仍只按需加载
- [x] 4.5 测试 95% 边界、自动压缩后仍超限、拒绝前不持久化、失败无半条 assistant、HTTP/SSE 同错误、跨用户和模型/摘要失败

## 5. 记忆 API 与前端 store

- [x] 5.1 实现 `PUT /chat/sessions/{id}/memory` 与 `POST /chat/sessions/{id}/memory:compact`，返回刷新后的详情并覆盖 401/403/422、空边界幂等和 owner scope
- [x] 5.2 扩展所有 session DTO mapper/list/detail/create/append/clear 返回记忆字段，确保 capability 缺失时明确失败而不猜窗口
- [x] 5.3 实现前端 typed chatClient 的 update/compact 和 Pinia actions，以服务端详情对账 sessions/selected detail，且不写 localStorage
- [x] 5.4 运行前端 store/client 测试并确认 P17 未新增 P19 composer UI 或移动替代流程

## 6. 完整验证、规格同步与归档

- [x] 6.1 在临时 SQLite 上运行 `uv run alembic upgrade head`，并运行 backend `uv run ruff check .`、`uv run pyright`、`uv run pytest`
- [x] 6.2 运行 `npm run contracts:typecheck`、`npm run contracts:test`、`npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build` 和 `npm run frontend:test:secret`
- [x] 6.3 运行 `$openspec-verify-change`，修复全部 CRITICAL 并处理 WARNING，再运行 `openspec validate --all` 与 `git diff --check`
- [x] 6.4 所有门禁通过后同步 delta specs 到主规格，归档 `add-session-memory-modes` 并再次运行 `openspec validate --all`
