# 前端工程基础

本 workspace 提供 Vue 桌面 Web 骨架、严格公开配置边界，以及 typed `apiClient`/`sseClient` transport。HTTP client 解包共享 envelope；SSE parser 支持跨 chunk frame，并只返回 `@super-ai/api-contracts` 的事件联合。

后续功能不得复制私有 envelope 或 event union，必须先扩展 contracts workspace。当前页面仍只表示工程基础可运行；认证、聊天、知识库和 AIOps 产品能力尚未实现。

```bash
npm run dev
npm run typecheck
npm run test
npm run build
npm run test:secret
```
