# 中文桌面工作台壳

本 workspace 提供 Vue 桌面 Web 认证工作台壳、严格公开配置边界，以及 typed `apiClient`/`sseClient` transport。`/login` 与 `/register` 连接真实认证 API；受保护的 `/chat`、`/knowledge`、`/aiops`、`/mcp` 共用桌面 WorkspaceLayout。刷新时通过 `/auth/me` 恢复认证，登出和 401 会清理本地受保护内存 store；localStorage 只保存 bearer token。

后续功能不得复制私有 envelope、Auth payload 或 event union，必须先扩展 contracts workspace。当前业务路由是明确占位页：Chat、知识库、AIOps 和 MCP 产品能力尚未实现。

```bash
npm run dev
npm run typecheck
npm run test
npm run build
npm run test:secret
```
