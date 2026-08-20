# 最终 Chat 工作区与引用规格

## Purpose

本能力把服务端持久会话、Agent SSE、Prompt/Skill、会话记忆、工具审计与知识引用组合为当前最终桌面 Chat 工作区，并保证所有可见领域状态都来自真实 API/SSE。

## Requirements

### Requirement: Chat 使用 conversation-first 固定桌面布局
`/chat` SHALL 使用全局左侧会话栏、中央 conversation 主区和独立右侧 Prompt/Skill sidebar/disclosure。会话栏 MUST 提供真实列表、新建、切换和删除；中央 transcript MUST 局部滚动且 composer 始终可见；Chat 主区 MUST NOT 再嵌套第二个历史侧栏。空会话 transcript MUST 保持真正空白，不渲染醒目空状态图标或绿色占位。当前验收只面向桌面浏览器。

#### Scenario: 进入 Chat 工作区
- **WHEN** 已认证用户进入 `/chat`
- **THEN** 全局左栏显示服务端会话，中央显示唯一 transcript/composer，右侧显示可折叠配置区域

#### Scenario: 空会话
- **WHEN** 当前会话没有历史消息且未开始流式回合
- **THEN** transcript 保持空白，不显示空状态插图、彩色占位卡或第二会话栏

### Requirement: 会话与组合状态以服务器为事实来源
Chat Pinia 状态 SHALL 管理 sessions、active session/messages、configuration、toolAudits、liveToolCalls 与 references；新建、切换、删除、Prompt/Skill、memory 和 complete 后历史 MUST 通过真实 API 对账。Chat、Prompt、Skill、引用和工具状态 MUST NOT 写入 localStorage；认证失效与 logout MUST 清理全部受保护状态。

#### Scenario: complete 后对账
- **WHEN** SSE 收到唯一 complete
- **THEN** store 重新读取当前会话详情与工具审计，并以服务端消息 metadata 替换临时当前轮状态

#### Scenario: 删除当前会话
- **WHEN** 用户确认删除 active session
- **THEN** 服务端删除成功后 store 移除该会话，并确定性选择剩余首个会话或创建新会话，不保留已删除消息

### Requirement: Composer 正确处理键盘与输入法
Composer SHALL 使用不可由用户 resize 的 textarea。非 composing 状态下 Enter MUST 发送非空内容，Shift+Enter MUST 插入换行；IME composing 期间 Enter MUST NOT 发送。streaming 或空白内容时发送动作 MUST 禁用，错误后用户内容 MUST 保留以便重试。

#### Scenario: 中文输入法确认候选
- **WHEN** textarea 正处于 IME composing 且用户按 Enter
- **THEN** composer 不发送消息并保留输入内容

#### Scenario: Shift Enter
- **WHEN** 用户按 Shift+Enter
- **THEN** textarea 插入换行且不开始 SSE 请求

### Requirement: SSE 事件按读取顺序更新可见状态
Store MUST 使用共享 SSE union 并按 `for await` 顺序处理事件。每个 `content.delta` 字符写入可见正文后 MUST 通过 `setTimeout` 等待约 28 ms，再读取后续事件；MUST NOT 虚构 requestAnimationFrame 或独立消费队列。reasoning、tool、reference、complete 与 error 不做字符延迟。缺少 complete 的流 MUST 进入可恢复错误状态。

#### Scenario: 字符节奏可验证
- **WHEN** 流连续产生三个正文字符
- **THEN** 每个字符先更新状态、再等待约 28 ms，fake timer 可逐步观察三个有序状态

#### Scenario: 跨 chunk SSE frame
- **WHEN** reference、tool 或正文 frame 被网络 chunk 拆分
- **THEN** transport 只在完整 frame 后产生一次 typed event，store 按 event sequence 处理且不重复

### Requirement: 每轮 live references 严格隔离
每个新回合开始前 MUST 清空 live references。实时引用只来自本轮 `reference.source`；reload MUST 只从对应 assistant message metadata 恢复。第二轮未产生引用时 MUST NOT 显示第一轮引用。

#### Scenario: 两轮引用隔离
- **WHEN** 第一轮产生引用而第二轮未产生引用
- **THEN** 第二轮 streaming 与 complete 后均不显示第一轮引用，第一轮 assistant 仍可显示自身 metadata 引用

### Requirement: 消息正文使用安全 Markdown
user 与 assistant 消息 SHALL 使用专业、正文自适应宽度的气泡。Markdown MUST 经 marked 解析并由 DOMPurify 清洗，且 MUST 禁用或移除不可信 raw HTML、脚本、事件属性和危险 URL；纯文本语义与代码块仍可读。

#### Scenario: 消息包含恶意 HTML
- **WHEN** 消息正文包含 script、onclick、iframe 或 javascript URL
- **THEN** 渲染结果不执行也不保留危险内容，并继续显示安全 Markdown 正文

### Requirement: reasoning 与工具生命周期默认折叠
真实 reasoning 与 tool.call lifecycle SHALL 在当前轮和历史审计中以可访问 disclosure 展示。工具输出 MUST 默认折叠，页面只显示 toolName、started/completed/failed、耗时和安全摘要；MUST NOT 展示 raw JSON、完整参数值、完整工具输出或凭据。

#### Scenario: MCP 工具成功完成
- **WHEN** 当前轮收到同一 toolCallId 的 started 和 completed
- **THEN** 页面更新同一折叠项的文字状态并只显示安全摘要

#### Scenario: 模型没有 reasoning
- **WHEN** 本轮未收到 reasoning.delta
- **THEN** 页面不渲染空 reasoning 面板或合成思考内容

### Requirement: 引用卡片展示完整检索证据
每条 assistant 消息或当前 live turn SHALL 最多显示五条引用，按 rerankRank 升序、rerankScore 降序和 chunkId 稳定排序。卡片 MUST 显示 source、excerpt、documentId、knowledgeBaseId、vector/BM25/RRF/rerank rank 与 score，并使兼容 score 等于 rerankScore。未参与 vector 或 BM25 分支时 rank/score MUST 显示“未命中”，不得伪造 0 排名。详情 disclosure SHALL 展示 metadata 与阶段轨迹，并可导航到当前 owner 的知识文档。

#### Scenario: 单分支未命中
- **WHEN** 引用的 vectorRank/vectorScore 为 null 而 BM25 与 rerank 有值
- **THEN** 卡片显示 vector“未命中”并显示真实 BM25、RRF 与 rerank 证据

#### Scenario: 引用超过五条
- **WHEN** 当前轮收到六条以上引用且顺序未按 rerank 排列
- **THEN** UI 确定性排序并只展示前五条，不修改原始分数

### Requirement: Prompt Skill 与记忆操作可恢复
右侧配置 SHALL 支持 Prompt 单选/创建/编辑/删除、Skill 多选/`SKILL.md` 上传/删除；composer 邻近区域 SHALL 显示 memory mode、contextUsagePercent、contextTokens/contextWindowTokens、canCompact，并支持 manual compact。操作失败 MUST 保留服务端最后成功状态并提供中文可重试错误，不得用静态资产替代。

#### Scenario: 更新记忆模式失败
- **WHEN** memory API 返回错误
- **THEN** UI 恢复服务端最后成功模式、保留会话消息并显示可重试错误

#### Scenario: 上传 Skill
- **WHEN** 用户选择合法 `SKILL.md` 并上传成功
- **THEN** sidebar 以服务端 configuration 响应更新技能列表和选择状态
