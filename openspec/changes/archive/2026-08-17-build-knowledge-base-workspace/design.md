## Context

见 `proposal.md` 的 Why。P08 已提供受保护桌面壳、typed transport、Pinia 清理注册机制和共享状态组件；P10/P11 已提供 owner-scoped 文档与持久索引 API，P09 的 background-job 列表可恢复 taskId 与文档关联。当前前端只有上传并创建任务的薄 client，`/knowledge` 仍指向占位页。

## Goals / Non-Goals

**Goals:**

- 在 Vue 3.5、Pinia 3 和共享 TypeScript contracts 上建立真实 API 驱动的 knowledge store。
- 将上传、覆盖、删除、预览、任务恢复/轮询/重试/重建组织为可测试的单向数据流。
- 在 WorkspaceLayout 的 edge-to-edge 画布中提供稳定的桌面有界滚动和中文可访问状态。
- 保持 bearer、401 清理、request-id 和统一 envelope 全部走现有 `apiClient`。

**Non-Goals:**

- 不新增知识库创建/删除、多知识库产品流程、搜索或聊天引用 UI。
- 不在知识页复制通用后台任务取消 API 或状态机。
- 不将知识领域数据写入 localStorage，不新增移动专用导航或替代布局。
- 不以 fake task、静态数组或浏览器持久化替代真实后端。

## Decisions

### Decision: 一个 owner-scoped knowledge store 组合多个 typed API

`knowledgeClient` 扩展为知识库/文档/预览/index task/background-job 的 typed facade；Pinia store 只保存服务器 DTO、界面选择和短生命周期请求状态。所有 HTTP 继续委托现有 `ApiClient` 解 envelope、注入 bearer 并处理 401。

选择该方案是因为工作区需要跨文档列表、详情和任务恢复保持一致状态，同时仍能把传输细节留在 client。备选的“每个组件自行 fetch”会产生重复轮询和难以统一清理的状态；GraphQL 或新增聚合后端超出本 change。

### Decision: 通过通用 background-job 列表恢复索引任务关联

初始化时读取 owner-scoped `/background-jobs`，筛选 `kind=document.index`、`resourceType=document_index_task` 且 payload 中 KB/document 与当前服务端文档匹配的记录，以 `updatedAt` 确定每文档最新 taskId，再调用既有 index-task GET 获取领域状态。新上传、重试和重建直接使用对应 API 返回的任务 DTO。

该方式复用 P09/P11 已有事实来源，无需为 P13 发明新的任务列表 endpoint。知识页不提供取消按钮；未来若需要取消，仍通过通用 background-job UI/能力实现。

### Decision: 单一 2 秒调度器轮询所有活动任务

store 在存在 pending/running 任务时维持一个 `setTimeout` 调度器，每轮并行刷新活动任务，终态后刷新文档列表并在无活动任务时停止。新消息/任务会重置下一轮，`reset()` 与组件卸载均清理 timer，并用 generation token 忽略清理后的迟到响应。

相比每个任务独立 interval，此方案更容易保证只存在一个 timer、避免重叠请求，并使 fake timer 测试稳定。约 2 秒是 UI 调度节奏，不承诺精确实时性。

### Decision: multipart 由共享 policy 驱动并保留可重放上传草稿

上传表单从 `KNOWLEDGE_UPLOAD_POLICY` 读取 accept、最大字节数和字段名。`fixed-character` 构造完整参数；其余策略构造仅含 strategy 的判别联合。发生 `BUSINESS_CONFLICT` 时 store 在内存保留 File 与不可变配置草稿，展示确认后以 `overwrite=true` 重放；取消确认立即丢弃草稿。

File 不写 localStorage。前端提示改善体验但不替代后端校验；所有服务端验证错误仍按统一 envelope 呈现。

### Decision: 视图按职责拆为工作区、上传表单、文档表和行内详情

`KnowledgeView` 负责初始化/释放；`KnowledgeUploadPanel` 负责文件与策略表单；`KnowledgeDocumentTable` 负责有界列表及确认动作；`KnowledgeDocumentDetail` 负责 metadata 与真实 preview。组件通过 store actions 交互，不自行保存领域副本。

列表容器采用 `min-height: 0`、`overflow-y: auto`；详情的 metadata/preview 使用独立 `max-height` 与滚动容器，表格外层 `overflow-x: auto`。所有异步状态复用共享状态组件或 `AsyncStatusBadge`，按钮具有文字和 aria 属性。

## Risks / Trade-offs

- [background-job payload 形状是 `unknown`] → client 使用窄化函数验证字符串字段，非法或越权关联直接忽略，不扩大 owner scope。
- [轮询与页面离开/登出竞态] → 单 timer、generation token 与 protected-store reset 共同停止后续更新。
- [上传成功但首次 index-task 创建失败] → 保留已上传文档、刷新列表并显示明确错误；用户可用“重新索引”恢复，不宣称跨请求原子性。
- [真实 Qwen/Milvus 不可用] → 自动化测试使用 typed transport fake；桌面 smoke 必须如实报告外部服务或凭据状态，不能伪造成功。
- [长文件名和 metadata 撑宽布局] → 单元格截断/换行与横向滚动容器共同约束，不依赖全页滚动兜底。

## Migration Plan

1. 扩展现有 typed knowledge client 与测试，不改变后端 endpoint。
2. 新增 Pinia knowledge store，并注册到 P08 protected-store 清理机制。
3. 新增工作区组件和组件测试，将 `/knowledge` 切换到真实视图。
4. 通过门禁与本地桌面 smoke 后同步规格并归档。

回滚时可将 `/knowledge` 路由恢复为占位组件并删除新增前端模块；后端 schema 与数据无需迁移。
