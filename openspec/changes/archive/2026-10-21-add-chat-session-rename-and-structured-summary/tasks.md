# Tasks

## 1. 会话重命名后端

- [x] 1.1 Repository 增加 owner-scoped `update_title`，更新标题与 `updatedAt`；单测覆盖成功、跨用户与不存在
- [x] 1.2 Service 增加标题规范化和 1..128 校验；空标题/超长返回 `VALIDATION_REQUEST_INVALID`
- [x] 1.3 新增 `PATCH /chat/sessions/{id}` 与 `UpdateChatSessionTitleRequest`，返回 `ChatSessionDetailData`；更新 OpenAPI/manifest
- [x] 1.4 修改自动标题逻辑：仅当标题仍为"新会话"时，首条 user 消息才自动生成标题；补"先重命名再发首条消息不覆盖"测试
- [x] 1.5 运行 chat API/Repository 目标 pytest 与契约测试

## 2. 结构化摘要

- [x] 2.1 更新 summarizer prompt，固定输出六段：对话目标 / 关键事实与标识 / 已做决定 / 工具与证据 / 未解决事项 / 风险与注意事项；空段写"（无）"
- [x] 2.2 在 memory service 增加摘要归一化：补齐缺失段、保持顺序；旧摘要无标题时不重写
- [x] 2.3 单测覆盖六段输出、空段、旧摘要兼容与摘要持久化；运行 chat memory 目标 pytest

## 3. 前端会话重命名

- [x] 3.1 `chatClient`/store 增加 `updateSessionTitle`/`renameSession`，成功后更新列表与详情
- [x] 3.2 `ChatSessionSidebar` 每项改为"选择 + 编辑"结构；行内 input，Enter 保存、Esc 取消；失败保留服务端标题
- [x] 3.3 组件/store 测试覆盖成功、校验失败、跨用户错误与不乐观更新

## 4. 摘要卡片

- [x] 4.1 `ChatSummaryPanel` 解析六段 Markdown；旧摘要按单一"摘要"展示；未知内容保留
- [x] 4.2 摘要卡片改为在选中会话行下方就地展开；同一时间仅一张；再次点击同一行或"收起"关闭
- [x] 4.3 组件测试覆盖六段顺序、旧摘要、展开/收起、单卡约束与压缩后刷新

## 5. 集成验证

- [x] 5.1 后端运行 `uv run ruff check .`、`uv run pyright`、`uv run pytest`（620 passed）
- [x] 5.2 前端运行 `npm run frontend:test`、`npm run frontend:typecheck`、`npm run frontend:build`（140 passed）
- [x] 5.3 真实 smoke：重命名会话 → 发送首条消息验证标题不被覆盖；压缩一次 → 生成六段摘要；SQLite 已确认保存 title 与 memory_summary
- [x] 5.4 运行 `npx --yes @fission-ai/openspec validate add-chat-session-rename-and-structured-summary --strict`

## Workflow follow-up

- 按仓库流程同步 WIKI（`scripts/sync_wiki.py active`），并运行 `npm run docs:build`
- 实现与验证完成后，使用 `openspec-verify-change` 复核，再归档该变更
