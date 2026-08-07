## MODIFIED Requirements

### Requirement: 后端提供最小且导入安全的应用
后端 SHALL 提供可显式创建的应用和 `/health` 健康检查；`/health` MUST 通过共享 OpenAPI path 合同登记，并返回包含 foundation 状态与 request ID 的统一成功 envelope。导入后端模块期间 MUST NOT 连接 SQLite、Milvus、LLM 或 MCP。项目内 Python 导入 MUST 使用 `super_ai` 包路径，不得使用 `src.super_ai`。

#### Scenario: 调用健康检查
- **WHEN** 测试通过 app factory 创建后端应用并请求 `/health`
- **THEN** 响应成功，返回 `{ok:true,data:{status:"ok"},meta:{requestId}}`，且 `X-Request-ID` header 与 meta 一致

#### Scenario: 仅导入后端包
- **WHEN** Python 进程导入 `super_ai` 及其应用模块
- **THEN** 导入完成且没有建立任何外部服务或数据库连接
