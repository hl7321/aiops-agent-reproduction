---
name: api-troubleshooting
description: 系统化排查 API 状态码、延迟、依赖、请求关联和契约不一致问题。
---

# API Troubleshooting

1. 确认 endpoint、method、状态码、request id 和发生时间。
2. 对比客户端请求、网关记录与服务端处理链。
3. 检查超时、重试、依赖健康和契约字段变化。
4. 优先给出可回滚、低风险的验证与缓解动作。
