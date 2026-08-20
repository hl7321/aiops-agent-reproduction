## ADDED Requirements

### Requirement: MCP 回退配置与凭据遵守本地安全边界
后端 SHALL 只从 `project.json` 与 `user.project.json` 的深合并结果读取 `clsMcpServer`，不得从 OS 环境变量获取 MCP 项目配置。模板中 baseUrl、secretId、secretKey 等凭据字段 MUST 为空，且前端构建 allowlist MUST NOT 暴露任何 MCP/CLS 字段。`clsMcpServer.baseUrl` 只表示主机上真实服务的回退地址，不得解释为已连通 profile。文档 MUST 明确官方 CLS MCP Server 在主机运行、不属于 Compose，并禁止把 token/secret 放入 MCP URL query；P18 MUST NOT 声称已完成 P26 的启动与凭据指南。

#### Scenario: 前端构建扫描 MCP sentinel
- **WHEN** 临时本地 JSON 的 mcp 或 clsMcpServer section 含唯一 sentinel 并执行前端生产构建
- **THEN** 构建成功且 dist 不包含 sentinel、baseUrl、secretId 或 secretKey 值

#### Scenario: 空 CLS baseUrl
- **WHEN** 深合并配置的 clsMcpServer.baseUrl 为空
- **THEN** 后端不创建回退 MCP client，不读取环境变量且不生成假连接
