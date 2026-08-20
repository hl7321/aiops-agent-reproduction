## Context

见 `proposal.md`。当前后端已提供 owner-scoped Chat REST/SSE、tool audit、Prompt/Skill configuration、session memory 和完整 Knowledge Retrieval citation；前端已有 typed clients 与基础 Chat/configuration stores，但 `/chat` 与 Workspace 会话栏仍是占位。现有 `ReferenceSource` 只传 id/title，无法满足实时与历史引用证据一致性。

## Goals / Non-Goals

**Goals:**

- 在不新增产品后端流程的前提下组合 P14–P18 能力，形成唯一、真实、可恢复的桌面 Chat 工作区。
- 让引用在 retrieval output、SSE、assistant metadata、Pinia 与 UI 之间使用同一 typed citation。
- 将布局、流消费、安全 Markdown、引用、工具状态和配置资产拆为可独立测试的小组件。
- 保持 tenant、凭据、日志、localStorage 与模块 import 安全边界不变。

**Non-Goals:**

- 不新增模型、retrieval、MCP、Prompt/Skill 或 memory 后端算法。
- 不新增独立搜索 API、移动专用导航、离线缓存、WebSocket、requestAnimationFrame 动画队列或前端领域持久化。
- 不把 raw tool arguments/output、reasoning 推断内容或用户不可信 HTML 暴露给页面。

## Decisions

### 1. 全局 Workspace 唯一拥有 Chat 会话栏

`WorkspaceLayout` 在 Chat route mount `ChatSessionSidebar`，该组件直接消费同一 `useChatStore`，负责 initialize、新建、切换和删除确认。`ChatView` 只拥有 transcript、composer 和右侧配置，不再复制 sessions 列表。

这使 route canvas 保持 conversation-first，也避免两套 active session 状态。备选是在 `ChatView` 内建第二侧栏；它会重复 P08 的全局布局边界，不采用。

### 2. Chat store 是页面组合状态，configuration store 继续负责资产写操作

`useChatStore` 保持 sessions、selectedDetail、liveContent/reasoning/toolCalls/references，并增加 `toolAudits`、串行 delay 注入和 complete 对账。Prompt/Skill CRUD 继续由 `useChatConfigurationStore` 管理，Chat 页面同时初始化两个 protected stores；“Pinia 保存 configuration”理解为 Pinia 状态体系，而不把两个清晰领域强行合并成超大 store。

两个 store 都只使用内存和真实 client，注册 protected cleanup。备选是把全部逻辑搬入单一文件；这会扩大耦合并使 CRUD 与流测试互相干扰，不采用。

### 3. `for await` 循环内直接等待 28 ms

`ChatStoreDependencies` 增加可注入 `sleep(milliseconds)`，默认用 `setTimeout` Promise。每个 `content.delta` 先 append，再 `await sleep(28)`；其他事件立即处理。测试注入 fake timers/受控 sleep，验证字符可见状态与下一 event 尚未被读取。

不建立 requestAnimationFrame、独立 event queue 或后台 consumer，因为用户要求当前实现严格由 async iterator 背压形成节奏。流收到 complete 后调用 `getSession` 与 `listToolCallAudits` 对账；缺 complete 进入 error。

### 4. Citation 在共享合同中只有一种完整形状

TypeScript `ChatReference` 直接等价于 `KnowledgeRetrievalCitation`；`ReferenceSourceEvent.data.source` 也使用它。Pydantic `ChatReference` 增加 metadata 与所有 stage rank/score，`ReferenceSource` 继承/复用同字段。Agent event mapper 用完整 model dump/validation，不再降级成 id/title。

SQLite 现有 JSON metadata 无需迁移；旧引用若缺字段将不满足新合同，这是从零项目在未发布阶段的有意收紧。`score == rerankScore` 在 Pydantic validator、TypeScript guard 和合同测试中校验。

### 5. 历史与 live turn 分开呈现，complete 后以服务端覆盖

历史 assistant message 的 references 只从其 metadata 读取；live references 在每次 `streamMessage` 开始同步清空。streaming 期间 UI 额外渲染临时 assistant 气泡；complete 对账后临时正文/references 不再作为历史来源，防止同一回答重复或跨轮继承。

### 6. 安全 Markdown 使用 renderer 禁止 raw HTML，再由 DOMPurify 防御纵深

新增纯函数 `renderSafeMarkdown(markdown)`：marked renderer 的 `html` 分支返回转义文本或空字符串，并禁止 `javascript:` 等危险链接；最终始终经 DOMPurify sanitize，明确限制标签/属性。组件只通过该函数结果使用 `v-html`。

仅依赖 DOMPurify 的备选也能移除 script，但 raw HTML 仍先进入解析树；双层边界更容易通过行为测试证明“不信任 raw HTML”。

### 7. 引用、工具与配置使用专责 disclosure

- `ChatCitationList`：规范化排序、最多五条、主卡片和 metadata/检索轨迹 details，null 显示“未命中”，文档导航使用 `/knowledge?knowledgeBaseId=...&documentId=...`。
- `ChatToolActivity`：按 toolCallId 合并 lifecycle，默认折叠，只显示安全 output 摘要；历史使用 owner-scoped audits。
- `ChatConfigurationSidebar`：Prompt 单选/CRUD、Skill 多选/上传/删除，所有失败通过全局 feedback，保留 store 中最后成功 DTO。
- `ChatMemoryControls`：memory mode 与占用率邻近 composer，失败后重新读取 active session 恢复服务端状态。

### 8. 桌面滚动和可访问性由 CSS 结构约束

Chat canvas 高度继承 Workspace 的 `minmax(0, 1fr)`；主区使用 `overflow:hidden`，transcript 使用 `overflow:auto`，composer 和右栏不随 transcript 滚走。textarea `resize:none`。所有 disclosure 使用原生 `details/summary`，状态具有中文文字，focus/reduced-motion 继续复用全局 tokens。

## Risks / Trade-offs

- [Risk] 每字符 28 ms 会主动对上游 async iterator 施加背压，长回答显示时间增加 → 严格遵循当前产品语义，并在 streaming 状态允许用户看到持续进度；不建立额外队列。
- [Risk] WorkspaceLayout 与 ChatView 同时初始化 store 可能产生重复请求 → 由 store 的单次 initialization promise 去重，两个组件只调用同一幂等入口。
- [Risk] 完整 citation 扩大 SSE 与 SQLite metadata 体积 → 每轮 UI 最多展示五条，retrieval 本身 topK 最大五；不保存原始文档正文之外的新副本。
- [Risk] marked/DOMPurify 与 happy-dom 行为存在差异 → 纯函数测试危险 payload，组件测试只验证 consumer-visible DOM；生产构建仍运行 secret scan。
- [Risk] 真实 Qwen/Milvus/MCP smoke 依赖本机服务和凭据 → 自动门禁使用 fake transport，真实 smoke 仅在可用时执行并如实记录，缺失时不阻塞可重复工程门禁。

## Migration Plan

1. 先扩展共享 citation 合同与后端序列化测试，再更新前端 store fixture，避免中间私有类型。
2. 以 TDD 增加 store 流节奏/隔离/对账行为和安全 Markdown、引用排序等纯边界。
3. 实现专责组件并替换 Workspace/Chat 占位，最后接 Prompt/Skill/memory 操作。
4. 运行 contracts、backend 相关测试和 frontend 全门禁；通过后同步 specs 并归档。
5. 回滚只需撤销 P19 代码与合同；无数据库 migration 或外部数据转换。
