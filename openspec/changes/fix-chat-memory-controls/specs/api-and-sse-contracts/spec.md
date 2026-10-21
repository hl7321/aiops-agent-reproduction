# Spec Delta

## ADDED Requirements

### Requirement: JSON body 请求必须声明 Content-Type

所有通过共享 API client 发送的 JSON 字符串 body 请求 SHALL 自动设置 `Content-Type: application/json`；调用方显式提供其他类型时 MUST 保留调用方设置。FormData、Blob 或 SSE 请求 MUST NOT 被强制改为 JSON。服务端 MUST 仅对 JSON Content-Type 解析 Pydantic body，非 JSON Content-Type MUST 返回共享 validation 错误。

#### Scenario: 浏览器同款 JSON PUT

- **WHEN** 前端通过共享 client 发送带 JSON 字符串 body 的 `PUT /chat/sessions/{id}/memory`
- **THEN** 请求携带 `Content-Type: application/json`，服务端返回 200 而不是 422

#### Scenario: 非 JSON body 不被改写

- **WHEN** 调用方发送 FormData、Blob 或显式指定其他 Content-Type
- **THEN** 共享 client 不覆盖该 Content-Type

#### Scenario: 非 JSON Content-Type 被拒绝

- **WHEN** 客户端用 `text/plain` 发送 memory PUT body
- **THEN** 服务端返回 `VALIDATION_REQUEST_INVALID` 422，且前端共享 client 的正常 JSON 请求不受影响
