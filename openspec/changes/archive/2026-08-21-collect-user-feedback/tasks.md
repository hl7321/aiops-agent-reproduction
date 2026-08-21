## 1. 共享合同与验收测试

- [x] 1.1 先为 target/rating/reason 允许集合、Feedback DTO、subjectId 可空映射和三条 operation 编写 contracts 失败测试
- [x] 1.2 在 `packages/api-contracts` 实现 feedback typed entrypoint、导出、manifest/OpenAPI operation 与共享认证/错误声明
- [x] 1.3 先为四类目标、upsert、删除、恢复、跨租户、父资源缺失、输入校验和日志脱敏编写后端验收测试
- [x] 1.4 先为 feedback client/store/control、Chat/AIOps 接入、失败保留草稿和 protected cleanup 编写前端失败测试

## 2. 数据库与 Repository 边界

- [x] 2.1 新增 `user_feedback` Alembic 迁移，包含非空 subject_key、owner 复合唯一键、查询索引和可逆 downgrade
- [x] 2.2 增加不可变 Feedback record、Repository Protocol 与 SQLite adapter，实现 owner-scoped list、原子 upsert 和不可枚举 delete
- [x] 2.3 为 Chat/diagnostic Repository 增加 SQL 内含 owner 条件的 `get_message`、`get_step`、`get_report` 参数级读取并补合同测试
- [x] 2.4 验证 fresh database upgrade、metadata 与迁移一致、subject 空串归一化和并发 upsert 唯一性

## 3. 后端反馈服务与 API

- [x] 3.1 实现四类 target resolver，验证 assistant role、citation chunkId、diagnostic step/report 和 subject 形状且不执行无 scope 探测
- [x] 3.2 实现 FeedbackService 的 trim/长度/枚举校验、目标先验证、恢复、upsert 和 owner-scoped 删除语义
- [x] 3.3 增加 Pydantic feedback contracts、DTO mapper、依赖注入和认证 FastAPI router，复用统一 envelope/requestId/error
- [x] 3.4 将 feedback model/router 接入应用和 migration metadata，确保 import/普通启动无数据库或外部副作用
- [x] 3.5 通过后端测试证明四类 target ownership、不可枚举 404、父资源删除/不存在、upsert/delete/恢复和日志不含正文 sentinel

## 4. 前端通用反馈能力

- [x] 4.1 实现 typed `feedbackClient` 和 protected Pinia feedback store，以服务器响应维护 saved state 并按 target group 去重恢复请求
- [x] 4.2 实现可访问 `UserFeedbackControl`，支持赞同/反对、问题类型、评论、纠正、更新、删除和明确 loading/error/saved 状态
- [x] 4.3 确保提交/删除失败保留草稿及服务器旧值，不乐观伪造成功、不写 localStorage，登出只清内存 store
- [x] 4.4 用组件/store 测试覆盖首次恢复、更新、删除、失败重试、输入限制、ARIA 文字和 protected cleanup

## 5. Chat 与 AIOps 页面接入

- [x] 5.1 在持久 assistant answer 上接入 message feedback，并确保 live 临时消息获得服务器 message id 前不可提交
- [x] 5.2 在每条 citation 上以 assistant message id + chunkId 接入独立反馈，验证会话切换和多轮恢复不串数据
- [x] 5.3 在持久 diagnostic step 与 diagnostic report 上接入反馈，排除 plan/tool/evidence/status 等非目标 timeline item
- [x] 5.4 补齐 Chat/AIOps 页面测试，覆盖重新打开恢复、四类控件交互、失败可重试和无 raw JSON/正文日志泄漏

## 6. 验证、同步与归档

- [x] 6.1 执行 `cd apps/backend && uv run alembic upgrade head && uv run ruff check . && uv run pyright && uv run pytest`
- [x] 6.2 执行 `npm run contracts:typecheck && npm run contracts:test && npm run frontend:typecheck && npm run frontend:test && npm run frontend:build && npm run frontend:test:secret`
- [x] 6.3 执行 `$openspec-verify-change`，修复全部 CRITICAL 并处理 WARNING 后重新验证
- [x] 6.4 执行 `openspec validate --all` 与 `git diff --check`，同步 delta specs 并用 `$openspec-archive-change` 归档
- [x] 6.5 检查归档和工作树后按 Conventional Commits 提交 P24，记录 commit id 与保存位置
