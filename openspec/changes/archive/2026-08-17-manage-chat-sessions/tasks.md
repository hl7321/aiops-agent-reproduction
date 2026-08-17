## 1. 共享合同与失败测试

- [x] 1.1 先为 ChatSession、ChatMessage、role、typed metadata/reference、六种操作 DTO 编写 contracts 失败测试
- [x] 1.2 先为六条聊天 OpenAPI path 的 method、operationId、成功类型、BearerAuth、401/403 和 append 422 编写失败测试
- [x] 1.3 实现并导出共享聊天类型、常量与机器可读 path，使 contracts typecheck/test 通过
- [x] 1.4 增加仓库策略测试，禁止前端私有聊天 payload、localStorage 聊天领域数据和后端临时合同结构

## 2. Alembic 与持久化边界

- [x] 2.1 先编写 fresh migration、downgrade/upgrade、ORM metadata 一致性、索引、外键级联和 import-safety 失败测试
- [x] 2.2 新增 `20260817_0006_manage_chat_sessions` Alembic revision，建立规范化 chat_sessions/chat_messages 表、owner 索引和 sequence 唯一约束
- [x] 2.3 先为 frozen records、Repository Protocol、UTC/JSON round-trip、owner 参数顺序和确定性排序编写失败测试
- [x] 2.4 实现 Chat records/Repository Protocol 与 `super_ai.memory.extended_sqlite` adapter，确保所有父子 SQL 显式 owner scoped
- [x] 2.5 补齐并发 append 唯一 sequence、异常回滚、clear sequence 重置和 delete cascade 测试并修复实现

## 3. 领域服务与 HTTP API

- [x] 3.1 先编写两个用户的创建、列表、详情、追加、清空、删除、跨 owner 与不存在父资源一致 403 的服务/API 失败测试
- [x] 3.2 先编写首条 user 标题空白规范化、48 Unicode 字符边界、非 user 不生成、后续 user 不覆盖和 clear 后重生标题测试
- [x] 3.3 实现 ChatService、Pydantic 请求/响应模型、Repository dependency 和六条 FastAPI 路由，复用统一 envelope/error/request-id
- [x] 3.4 在单一请求事务中完成 append 的 sequence、消息、标题和 updatedAt 更新，并证明失败整体回滚
- [x] 3.5 验证列表使用 `updatedAt DESC, id DESC`、详情消息 sequence 升序、metadata 完整 round-trip 和删除成功 payload
- [x] 3.6 增加 401、422、OpenAPI/共享 DTO 序列化一致性以及“追加不调用 LLM/Milvus/MCP/SSE”的边界测试

## 4. 前端 transport 与受保护 store

- [x] 4.1 先为 chatClient bearer/envelope、list/detail/create/append/clear/delete 请求与共享类型编写失败测试
- [x] 4.2 实现 typed chatClient，复用公共 ApiClient，禁止复制私有合同或将聊天数据写入 localStorage
- [x] 4.3 先为 chatStore 的服务端对账、选择状态、操作后刷新、错误状态与 owner 数据清理编写失败测试
- [x] 4.4 实现 Pinia chatStore 并登记 protected-store 清理；401/logout 清除内存状态但不删除服务端数据

## 5. 门禁、验证与归档

- [x] 5.1 在临时 SQLite 上运行 `uv run alembic upgrade head`，并运行 backend `uv run ruff check .`、`uv run pyright`、`uv run pytest`
- [x] 5.2 运行 `npm run contracts:typecheck`、`npm run contracts:test`、`npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build`
- [x] 5.3 运行 `openspec validate --all` 与 `git diff --check`，并检查未覆盖或误改既有 P13 工作区变更
- [x] 5.4 使用 `$openspec-verify-change` 核对完整性、正确性和设计一致性，修复全部 CRITICAL 并重新运行受影响门禁
- [x] 5.5 验证通过后同步 `chat-session-management` 与 `api-and-sse-contracts` delta specs，并使用 `$openspec-archive-change` 归档本 change
