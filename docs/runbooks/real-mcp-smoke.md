# 真实 MCP discovery 与 Chat 调用 smoke

P18 的自动化测试通过可注入 client 验证 owner scope、URL 校验、timeout/retry、冲突、SSE 与审计脱敏，但这不等于官方 CLS MCP Server 已真实连通。

官方 `cls-mcp-server` 必须在主机运行，不得加入 `infra/compose.yaml`。P18 不提供服务安装、启动或腾讯云凭据注入教程；这些细节由 P26 完成。当前连接模型不支持自定义 headers，且完整 URL 会持久化并返回，因此禁止把 token、secret、password 或其他凭据写入 URL query。

具备真实主机服务时，通过 `/mcp` 页面创建连接并执行“真实检查”。只有响应状态为 `connected` 且工具列表来自当次 Server discovery，才能继续在 `/chat` 发起一个明确需要该工具的问题。验收应确认：

- Chat 由模型自主选择工具，不在模型前预调用；
- SSE 产生同一 `toolCallId` 的 started/completed 或 started/failed；
- 工具审计只保存工具名、参数键、状态、耗时和安全摘要；
- 日志、SSE 与审计不包含完整参数值、工具输出或 URL query；
- MCP Server 不可用时显式失败，不生成假回答。

## 本次状态

**2026-08-20：未执行。** 当前 ignored 深合并配置中的 `clsMcpServer.baseUrl` 为空，因此没有可连接的官方 CLS MCP 主机服务地址。自动化 fake client 测试已通过，但不能替代真实连通性结论。
