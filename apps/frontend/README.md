# 中文桌面工作台壳

本 workspace 提供 Vue 桌面 Web 认证工作台、严格公开配置边界，以及 typed `apiClient`/`sseClient` transport。`/login` 与 `/register` 连接真实认证 API；`/knowledge` 已连接文档与索引 API；`/mcp` 已连接 owner-scoped MCP CRUD/check API，支持编辑、启停、SSE/Streamable HTTP 和真实发现工具展示。刷新时通过 `/auth/me` 恢复认证，登出和 401 会清理本地受保护内存 store；localStorage 只保存 bearer token。

后续功能不得复制私有 envelope、Auth payload 或 event union，必须先扩展 contracts workspace。`/chat`、`/knowledge`、`/aiops` 与 `/mcp` 均消费真实后端 API/SSE；页面不把领域数据保存到 localStorage，也不提供假工具、假日志或假历史。真实外部链路仍需本机服务和凭据，自动化组件测试不等于桌面真实验收。

```bash
npm run dev
npm run typecheck
npm run test
npm run build
npm run test:secret
```
