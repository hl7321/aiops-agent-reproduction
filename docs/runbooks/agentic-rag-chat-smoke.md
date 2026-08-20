# Agentic RAG Chat 真实 smoke

> 状态：**已于 2026-08-18 执行通过**。真实凭据仅来自被 Git 忽略的本机 JSON，未输出或提交。

## 验证范围

- 使用 `create_configured_app` 启动主机 FastAPI，并连接真实 Qwen 与本机 Compose Milvus。
- 通过真实注册、登录和会话 API 创建一次性 smoke 会话。
- 向流式消息 API 提交要求查询当前 UTC 时间的问题，由 Qwen Agent 自主调用
  `get_current_time`，未在 Agent 前固定执行知识检索。
- 检查共享 SSE 的 sequence 从 1 连续递增、工具生命周期为
  `started → completed`、正文按 Unicode 字符发送且 `complete` 恰好出现一次。
- 通过审计 API 确认工具记录为 `completed`，通过会话详情确认最终仅保存完整的
  user/assistant 消息；结束后删除 smoke 会话并撤销认证 session。

本次结果包含 45 个 SSE 事件与 42 个正文 Unicode 字符；工具审计名称为
`get_current_time`。执行期间发现 LangChain 的真实 `on_tool_end` 输出是
`ToolMessage`，修复为先规范化成共享合同允许的 JSON，再发送 SSE 和提取引用。

## 安全边界

运行日志只记录请求路径、工具参数键、生命周期、耗时和异常类型/验证字段路径；不得记录
prompt、query、参数值、工具输出、模型正文、bearer token 或 API key。自动化 fake 测试用于
稳定验证失败与边界场景，但不替代本页的真实连通证据。

smoke 完成后已停止 FastAPI 和五个 Compose 容器；Docker 卷、镜像及 ignored 本机配置保留，
后续需要时可重新启动。
