# Design

## Context

见 `proposal.md - Why`。问题已经用真实后端复现：JSON Content-Type 返回 200，`text/plain` 或不传返回 422。当前共享 `api.request` 没有设置 Content-Type，业务 client 也没有补，导致浏览器默认的 `text/plain` 触发 422。

需求见 `specs/api-and-sse-contracts/spec.md`。

## Goals / Non-Goals

**Goals：**

- 修复共享 client 的 JSON 请求头契约；
- 用前端与后端两侧的真实测试锁住该契约；
- 不改变任何记忆/压缩业务语义。

**Non-Goals：**

- 不引入有效记忆窗口，不改变 70%/95% 阈值；
- 不改上下文占用展示、DTO 或配置；
- 不改后端生产代码。

## Decisions

### 1. 在共享 ApiClient 统一补 JSON Content-Type

`api.request` 在以下条件同时成立时设置 `Content-Type: application/json`：

- `init.body` 是字符串；
- 调用方没有显式提供 Content-Type。

FormData、Blob 或已有 Content-Type 一律保持原样。

备选：每个业务 client 自己设置。会重复且容易漏，正是这次 422 的成因。

### 2. 前后端各写真实契约测试

- 前端：`apiClient` 测试断言实际发出的 header；`chatClient` 测试断言 memory PUT 的 URL、method、body 和 Content-Type。
- 后端：使用真实 FastAPI 应用与测试数据库，发送 `application/json` 断言 200；发送 `text/plain` 断言 422，明确契约边界。

不使用只检查 mock 调用参数的虚假测试；后端测试走真实请求解析。

### 3. 不碰后端生产代码

这次只改共享传输层与测试。记忆窗口、压缩阈值、DTO 与配置全部保持原状。

## Risks / Trade-offs

- **误伤非 JSON body**：通过 body 类型判断并保留显式 Content-Type，补 FormData/显式类型测试。
- **只修一个调用点**：在共享 client 修复，覆盖所有 JSON body 请求。
- **前后端测试重复**：前端锁请求形状，后端锁服务端解析边界，两者职责不同。

## Migration Plan

无数据库、配置或 API 迁移；回滚只需恢复前端代码。

## Open Questions

（无）
