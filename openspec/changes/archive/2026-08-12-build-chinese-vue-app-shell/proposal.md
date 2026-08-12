## Why

现有前端只有 foundation 展示页，虽然已经具备真实认证 client 和 typed transport，但缺少可承载后续 Chat、知识库、AIOps 与 MCP 能力的路由、认证工作台和统一交互基础。现在需要先建立可测试的桌面 Web 应用壳，确保后续产品提案沿用一致的认证、状态、布局和数据清理边界。

## What Changes

- 建立 Vue Router + Pinia 的中文桌面工作台，区分 publicOnly 认证路由与受保护业务路由，并实现首次导航认证恢复和安全 redirect。
- 让登录、注册、认证恢复和登出连接 P04 真实 API；401 与登出统一清理客户端受保护状态，但不删除服务端业务数据。
- 建立 WorkspaceLayout：左侧 rail、Chat 专属会话区域、账号与登出、顶栏标题、服务状态和 edge-to-edge 路由画布。
- 建立受保护 store 清理注册机制和内存态 protectedData；localStorage 仍只允许保存 bearer token。
- 提供 loading、empty、error、feedback 与 async status 等可访问共享组件，以及专业克制的中文设计 tokens、Lucide 图标、焦点与 reduced-motion 规则。
- 为 `/chat`、`/knowledge`、`/aiops`、`/mcp` 提供明确的占位路由，不声称后续业务能力已经实现；不新增移动端专用导航或替代流程。

## Capabilities

### New Capabilities

- `chinese-vue-app-shell`：定义桌面中文认证工作台的路由、认证恢复、受保护状态、布局、反馈和可访问交互要求。

### Modified Capabilities

- `user-authentication`：补充浏览器工作台对真实注册、登录、恢复、401 清理与登出的可观察行为。

## Impact

- 主要影响 `apps/frontend/src` 的入口、路由、认证 store、布局、页面、共享组件、样式和测试。
- 继续复用 `packages/api-contracts` 的 Auth DTO、HTTP envelope 与 SSE 事件，不复制私有 transport 合同。
- 前端测试增加 Vue 组件与路由挂载能力；后端 API 不新增产品 endpoint，仅回归 P04 认证测试。
- 后续 Chat、知识库、AIOps、MCP 提案将以本工作台壳、owner-safe 认证上下文和清理机制作为前端入口。
