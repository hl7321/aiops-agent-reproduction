## Why

知识文档、切分预览和持久索引已经具备后端能力，但 `/knowledge` 仍是占位页面，用户无法在桌面工作台中完成真实的上传、索引跟踪、预览、重试和删除闭环。现在需要以服务器为唯一事实来源，把这些既有合同组装成可用且可访问的知识库工作区。

## What Changes

- 将 `/knowledge` 从占位路由替换为连接真实后端 API 的中文桌面知识库工作区。
- 建立 typed `knowledgeClient` 与 Pinia knowledge store，统一管理知识库、文档、行内详情、切分预览、索引任务、轮询和覆盖确认。
- 使用共享上传策略约束 `.md`/`.pdf`、大小和切分参数；后端继续承担权威校验。
- 上传文档后显式创建首次索引任务，约每 2 秒轮询活动任务；支持失败原因、重试和手动重建。
- 为 hash 冲突覆盖和删除提供明确确认；操作成功后重新读取服务端列表。
- 建立桌面有界滚动、行内折叠详情、可访问中文状态和不依赖颜色的交互基础。
- 不使用 localStorage、静态数组或其他客户端持久化模拟知识领域数据；不新增移动专用流程，也不复制后台任务取消状态机。

## Capabilities

### New Capabilities

- `knowledge-base-workspace`: 规定真实 API 驱动的桌面知识库工作区、knowledge store、上传/预览/索引/覆盖/删除流程和布局可访问性。

### Modified Capabilities

- `chinese-vue-app-shell`: 将受保护的 `/knowledge` 从占位画布升级为真实知识库工作区，同时保持桌面 WorkspaceLayout 与认证清理边界。

## Impact

- 主要影响 `apps/frontend/src/knowledge`、Pinia stores、`/knowledge` 路由视图和相关组件测试。
- 复用 `packages/api-contracts` 中已有 knowledge、document-indexing 与 background-jobs 类型，不新增私有 payload 或事件联合。
- 复用 P10/P11 后端 API；只在合同或真实 smoke 暴露集成缺口时做最小兼容修复。
- 浏览器 smoke 需要本机后端、前端以及可用的 Qwen/Milvus 配置；无真实凭据或服务时必须如实记录阻塞，不得以 mock 代替。
