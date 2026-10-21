# 修复共享 JSON 请求的 Content-Type 契约

## Why

切换聊天记忆模式返回 422，根因不是旧页面，而是共享 API client 只设置了 `Accept: application/json`，没有设置 `Content-Type`。浏览器对字符串 body 自动发送 `text/plain;charset=UTF-8`，FastAPI 无法解析成 Pydantic body。

实测：

- `Content-Type: application/json` → 200
- `Content-Type: text/plain;charset=UTF-8` → 422
- 不传 Content-Type → 422

这是所有通过共享 client 发送 JSON 字符串 body 的调用共同面临的问题，必须在传输层修一次，而不是在记忆控件里绕过。

## What Changes

**1. 共享 API client 修正 JSON Content-Type。**

- 当请求 body 是字符串且调用方未显式设置 `Content-Type` 时，自动设置 `application/json`。
- FormData、Blob 与调用方显式指定的其他 Content-Type MUST 保持不变。
- 影响面是所有 JSON body 请求，不限于记忆模式切换。

**2. 增加前后端契约测试。**

- 前端测试断言共享 client 发出的 JSON 请求携带正确 header；
- 前端 chat client 测试断言 `PUT /chat/sessions/{id}/memory` 的 body 与 Content-Type 同时正确；
- 后端 API 契约测试使用真实 FastAPI 应用，断言 JSON Content-Type 返回 200、非 JSON Content-Type 返回 422，证明前端修复与后端契约对齐。

非目标：

- 不新增或缩小有效记忆窗口，不改变 70%/95% 压缩阈值；
- 不修改上下文占用展示、DTO、配置或后端生产代码；
- 不处理聊天工具调用扇出、模型选择或 PkgId。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `api-and-sse-contracts`: JSON 字符串 body 请求必须声明 `Content-Type: application/json`。

## Impact

**前端**

| 文件 | 影响 |
|---|---|
| `apps/frontend/src/transport/apiClient.ts` | 为字符串 body 补 JSON Content-Type |
| `apps/frontend/src/transport/apiClient.test.ts` | 断言 header，且不覆盖 FormData/显式类型 |
| `apps/frontend/src/chat/chatClient.test.ts` | 断言 PUT memory 的 body 与 header |

**后端**

- **无生产代码改动**；只增加一个真实 API 契约测试，记录 JSON / 非 JSON 的行为边界。

**数据与配置**：无迁移、无新增字段。
