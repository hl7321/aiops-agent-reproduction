## Why

P14–P18 已分别提供服务端会话、流式 Agent、Prompt/Skill、记忆与真实 MCP 能力，但 `/chat` 仍是静态占位，用户无法在一个连贯桌面工作区中使用这些能力。P19 需要把既有真实 API/SSE 组合成当前最终 Chat 体验，并让知识引用在实时流和历史恢复中保留完整检索证据。

## What Changes

- 将真实会话列表、新建、切换和删除放入全局 Workspace 左侧会话栏，仅在 `/chat` 显示；Chat 主画布不再嵌套第二层历史栏。
- 建立 conversation-first Chat 主区：局部滚动 transcript、始终可见 composer、邻近记忆控制，以及独立 Prompt/Skill 右侧 disclosure。
- 扩展共享 Chat reference/SSE source 合同，使实时引用与 assistant metadata 都携带完整 retrieval citation、nullable 分支排名和分数。
- 让 Chat Pinia store 统一管理 sessions、active detail、configuration、tool audits、live tool lifecycle 和 references，并严格按 `for await` 顺序消费共享 SSE；每个正文字符更新后等待约 28 ms。
- 使用 marked 与 DOMPurify 安全渲染正文，禁用不可信 raw HTML；reasoning、工具生命周期和输出使用默认折叠的安全摘要视图。
- 提供最多五条、按 rerank 排序的引用卡片和检索轨迹 disclosure，并导航到当前 owner 的知识文档。
- 在同一工作区接入 Prompt 单选/CRUD、Skill 多选/上传/删除、memory mode 与 manual compact；错误可恢复且领域数据不写 localStorage。
- 增加键盘/IME、SSE 断帧、28ms fake timer、complete 对账、引用隔离、安全 Markdown、布局与组合操作测试；真实模型/MCP smoke 只在本机服务可用时如实执行。

## Capabilities

### New Capabilities

- `final-chat-workspace-and-citations`: 定义最终桌面 Chat 工作区、交互、流状态、安全渲染、工具视图、引用卡片和配置组合行为。

### Modified Capabilities

- `chinese-vue-app-shell`: 将 Chat 会话列表从占位区域升级为连接真实 store 的全局左栏，并锁定仅 `/chat` 可见的布局职责。
- `api-and-sse-contracts`: 扩展共享 ChatReference 与 reference.source，使完整 retrieval citation 在 TypeScript/Pydantic/SSE 中一致。
- `agentic-rag-chat-streaming`: 实时引用事件和成功 assistant metadata 必须携带同一轮完整检索证据，支持 reload 精确恢复。
- `chat-session-management`: Chat message metadata 的 references 扩展为完整、可追溯且 nullable rank 安全的 citation 形状。

## Impact

- 前端：`WorkspaceLayout`、`ChatView`、Chat/configuration stores、typed clients、SSE 消费与新增 Chat 专责组件及样式。
- 共享合同：Chat reference、reference.source 和合同测试；不新增独立搜索产品 API。
- 后端：仅调整现有 Chat/SSE 引用序列化形状及相应合同测试，不改变 Agent、retrieval、MCP 或持久化生命周期。
- 文档与 OpenSpec：新增最终 Chat 工作区规格和桌面 smoke 说明；Compose 与本地安全配置边界不变。
