# Tasks

## 1. 共享 API client

- [x] 1.1 在 `apiClient.request` 中为字符串 body 自动设置 `Content-Type: application/json`，不覆盖 FormData/Blob/显式类型；在 `apps/frontend/src/transport/apiClient.test.ts` 断言实际 header
- [x] 1.2 在 `apps/frontend/src/chat/chatClient.test.ts` 断言 `PUT /chat/sessions/{id}/memory` 同时发送正确 body 与 Content-Type
- [x] 1.3 运行相关 Vitest 与 `npm run frontend:typecheck`，确认无回归

## 2. 后端契约测试

- [x] 2.1 在 `apps/backend/tests/chat/test_api.py` 用真实 FastAPI 应用与测试数据库发送 `application/json` 的 memory PUT，断言 200 且模式更新
- [x] 2.2 同一接口发送 `text/plain`，断言返回 422 且错误为 `VALIDATION_REQUEST_INVALID`，明确服务端契约边界
- [x] 2.3 运行目标 pytest，确认测试走真实请求解析而非 mock

## 3. 集成验证

- [x] 3.1 在 `apps/backend` 运行 `uv run ruff check .`、`uv run pyright`、`uv run pytest`（615 passed）
- [x] 3.2 在仓库根运行 `npm run frontend:test`、`npm run frontend:typecheck`、`npm run frontend:build`（134 passed）
- [x] 3.3 实际调用后端三种 memoryMode（带 `application/json`）确认都返回 200
- [x] 3.4 运行 `npx --yes @fission-ai/openspec validate fix-chat-memory-controls --strict`

## Workflow follow-up

- 按仓库流程同步 WIKI（`scripts/sync_wiki.py active`），并运行 `npm run docs:build`
- 实现与验证完成后，使用 `openspec-verify-change` 复核，再归档该变更
