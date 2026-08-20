# 最终 Chat 桌面工作区 smoke

> 当前状态：2026-08-20 已完成真实 Qwen 普通问答，以及真实 Qwen Embedding、Milvus 与 Qwen Rerank 的自主知识检索问答。当前本机没有 enabled MCP connection，默认 CLS MCP URL 也未配置，因此真实 MCP smoke 未执行；自动化 fake 测试不等于真实 MCP 连通。

## 前置条件

- `config/project.json` 与 `config/user.project.json` 是被 Git 忽略的本机配置，Qwen API key 只填写在 user 配置，不输出到终端或日志。
- 运行 `docker compose -f infra/compose.yaml up -d etcd minio milvus attu`，确认 Milvus health 正常。Alertmanager 不是 Chat smoke 的必需依赖。
- 在 `apps/backend` 运行 `uv run alembic upgrade head`，再通过配置化 app factory 启动主机 FastAPI；在仓库根运行 `npm run frontend:dev`。
- 若验证 MCP 自主工具，先在主机启动真实 MCP Server，再通过 `/mcp` 创建、启用并实际检查连接。禁止把凭据放入 URL query。

## 场景一：普通问答

1. 使用真实注册/登录进入 `/chat`，确认左栏可新建、切换和删除服务端会话。
2. 输入不需要外部工具的普通问题，确认 Agent 可自主选择不调用知识或 MCP 工具。
3. 检查正文逐字符平滑呈现、composer 始终可见，结束后页面从服务端历史对账。
4. 刷新页面，确认消息来自 Chat API；空新会话 transcript 保持空白，不出现产品占位图。

## 场景二：自主知识与 MCP 工具问答

1. 在 `/knowledge` 准备 owner-scoped 且已成功索引的文档，再返回 `/chat` 提出需要知识依据的问题。
2. 确认模型自主调用 `knowledge_retrieval`，页面只展示安全工具摘要；引用最多五条并显示 vector/BM25/RRF/rerank 的真实排名和分数，未参与分支显示“未命中”。
3. 展开引用详情检查 metadata 与检索轨迹，并通过链接导航到当前 owner 的知识文档。
4. 对真实 enabled MCP 连接提出适用问题，确认真实工具 discovery/call、SSE lifecycle 和 owner-scoped audit 一致；不得使用静态工具或假结果替代。
5. 开启第二轮不需要引用的问答，确认不会继承上一轮引用；刷新后每条 assistant 只恢复自身 metadata 中的 references/toolCallIds。

## 安全检查

- Markdown 必须经 marked 解析与 DOMPurify allowlist 清洗，不执行 raw HTML、脚本或危险链接协议。
- 页面不得展示 tool input/output 的 raw JSON，不记录 prompt、query、完整参数、模型正文、token 或 API key。
- Prompt/Skill/memory 写操作失败时展示可恢复错误，并保持最后一次服务端成功 DTO；Chat/Knowledge/MCP 领域数据不得写入 localStorage。

## 2026-08-20 实测记录

- 使用一次性本机账号通过真实注册/登录进入桌面 `/chat`，普通问题“请只用一句中文介绍你自己，不要调用任何工具”成功返回，页面没有产生工具活动。
- 上传并成功索引 `final-chat-workspace-smoke.md` 后，询问停止 Compose 的命令。模型自主调用 `knowledge_retrieval`，回答 `docker compose -f infra/compose.yaml stop`，并展示两条真实引用。
- 首条引用显示 rerank rank 1 / score 0.8818、vector rank 2 / score 0.4011、BM25 rank 1 / score 8.1996、RRF score 0.0325；没有用假排名或 fallback 分数。
- 引用链接成功导航到 owner-scoped 文档，并自动展开 metadata 与两段实际切分预览。
- 随后发送“不使用任何工具，只回答：收到”，该轮没有工具活动或引用；刷新后连续三条 assistant 消息的引用分布为 0 / 1 / 0，证明引用不会跨轮继承，且 complete 后及 reload 均以服务端历史对账。
- 实测发现并修复两项集成问题：并发初始化可能重复创建空会话；引用导航最初只进入知识页、未自动展开目标文档。两项均增加回归测试。
- 真实 MCP smoke 未执行：数据库中没有 enabled MCP connection，默认 CLS MCP URL 未配置。P18 的可控 fake transport 测试只验证代码边界，不能替代真实 MCP Server；待按 P26 配置并启动官方服务后复测。

## 收尾

如需清理，可删除一次性会话和 smoke 文档并 logout 撤销认证 session。执行 `docker compose -f infra/compose.yaml stop` 可停止容器；镜像、卷和 ignored 本机配置会保留，后续可再次启动。本次记录保留本机 smoke 数据，便于复核引用与服务端恢复行为。
