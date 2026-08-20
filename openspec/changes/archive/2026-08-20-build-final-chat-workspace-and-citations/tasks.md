## 1. 完整引用合同

- [x] 1.1 先扩展 contracts 失败测试，覆盖 ChatReference/reference.source 完整 citation、nullable 分支、`score===rerankScore` 和不完整 payload 拒绝。
- [x] 1.2 更新 TypeScript contracts、Pydantic models 与 SSE guard，使 Chat metadata、retrieval output 和 reference event 使用同一字段集合。
- [x] 1.3 先扩展后端 Agent event/runner 测试，再让实时 reference 与 assistant metadata 保留完整检索证据且两轮隔离。

## 2. Chat store 流状态

- [x] 2.1 先增加 store 失败测试，覆盖 initialize 去重、active session、tool audits、complete 服务端对账和受保护清理。
- [x] 2.2 先用 fake timer/受控 async iterator 证明每个正文字符更新后等待约 28 ms，且没有独立队列或 requestAnimationFrame 语义。
- [x] 2.3 实现串行 SSE reducer、可注入 sleep、live reasoning/tool/reference/error、缺失 complete 错误与两轮引用清理。
- [x] 2.4 增加历史引用恢复、删除 active 后确定性切换/创建和内存操作失败恢复测试与实现。

## 3. 安全消息与证据组件

- [x] 3.1 先增加恶意 HTML、危险 URL、Markdown 正文与代码块测试，再实现 marked + DOMPurify 的 `renderSafeMarkdown` 纯边界。
- [x] 3.2 先增加引用排序、最多五条、null“未命中”、metadata/阶段轨迹和知识文档导航测试，再实现 `ChatCitationList`。
- [x] 3.3 先增加 reasoning 缺省隐藏、tool lifecycle 合并、默认折叠和禁止 raw JSON 测试，再实现 `ChatToolActivity`。
- [x] 3.4 实现可访问的 user/assistant `ChatMessageBubble`，历史 assistant 只读取自身 metadata references/toolCallIds。

## 4. 会话栏与 conversation-first 布局

- [x] 4.1 先增加 Workspace 失败测试，覆盖真实会话列表、新建、切换、删除确认、仅 `/chat` 显示和无第二历史栏。
- [x] 4.2 实现 `ChatSessionSidebar` 并接入 `WorkspaceLayout`，移除占位图标、disabled 新建按钮和未实现文案。
- [x] 4.3 先增加空白 transcript、局部滚动、固定 composer、桌面三栏和 textarea `resize:none` 测试，再实现 Chat 主布局。

## 5. Composer、配置和记忆

- [x] 5.1 先增加 Enter、Shift+Enter、IME composing、空白/streaming 禁用和错误保留草稿测试，再实现 `ChatComposer`。
- [x] 5.2 先增加 Prompt 单选/CRUD 与 Skill 多选/上传/删除的组件测试，再实现独立 `ChatConfigurationSidebar`，失败保留最后成功 DTO。
- [x] 5.3 先增加 memory mode、context 占用率、manual compact 与失败恢复测试，再实现 composer 邻近 `ChatMemoryControls`。
- [x] 5.4 用 `ChatView` 组合 transcript、live turn、composer、配置、引用、工具和 feedback，并确保初始化使用真实 API。

## 6. 文档与验证

- [x] 6.1 更新中文 README 与 P19 桌面 smoke 说明，不声称未执行的真实 Qwen/Milvus/MCP 连通结果。
- [x] 6.2 运行 contracts typecheck/test、frontend typecheck/test/build/secret scan，修复全部问题。
- [x] 6.3 运行相关 backend pytest、Ruff、strict Pyright，确认完整 citation 序列化和 import-safety。
- [x] 6.4 运行 `openspec validate --all` 与 `git diff --check`，并在可用时执行普通问答及自主知识/MCP 工具桌面 smoke；不可用时明确记录未执行原因。
- [x] 6.5 使用 `$openspec-verify-change` 核对完整性、正确性和设计一致性，修复全部 CRITICAL/WARNING 并重新运行受影响门禁。

归档动作：验证通过后同步 delta specs，并使用 `$openspec-archive-change` 归档本 change；该生命周期动作不作为归档前任务复选框。
