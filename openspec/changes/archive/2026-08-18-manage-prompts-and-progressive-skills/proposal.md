## Why

P15 的 Chat Agent 已能持久对话并自主调用工具，但每轮仍使用固定系统提示词，用户也无法管理可按需加载的标准 Skill。现在需要建立 owner-scoped Prompt/Skill 资产和请求级装配边界，让模型获得可控个性化能力，同时避免把全部 Skill 正文预注入上下文。

## What Changes

- 新增每用户 Chat 配置、Prompt 与 Skill 的 SQLite 持久化和 owner-scoped CRUD；Prompt 单选、Skill 多选。
- 新增配置、Prompt 和 multipart `SKILL.md` 上传 API，并定义删除已选 Prompt 后回退为无用户 Prompt的确定语义。
- 校验 Skill 的严格文件名、UTF-8、大小、YAML frontmatter、规范化 name、description 与同用户唯一性。
- 每轮从服务端读取当前选择，按“平台安全规则 → 当前 Prompt → 选中 Skill 摘要目录”组装 system prompt，禁止用户 Prompt 改写 tenant/tool 安全边界。
- 新增绑定当前 owner 与本轮选择白名单的 `load_skill(name)` LangChain Tool；只有模型真实调用时才返回完整正文。
- 扩展共享 contracts、机器可读 OpenAPI 和前端 configuration client/store；最终侧栏与资产编辑 UI 留给 P19。
- 在 `docs/examples/skills/<name>/SKILL.md` 提供五个可上传的规范示例，但运行时不自动扫描或注册这些目录。
- 保持 reasoning 只透传模型真实内容，不接入静态项目 catalog、不做 Skill 全文预注入。

## Capabilities

### New Capabilities

- `prompt-and-progressive-skill-management`：定义 owner-scoped Prompt/Skill 资产、选择配置、上传校验、删除 fallback、前端状态和按需正文加载语义。

### Modified Capabilities

- `agentic-rag-chat-streaming`：把每轮 Agent 装配扩展为平台规则、用户 Prompt、Skill 摘要 catalog 与 owner-bound `load_skill` Tool，同时保持自主工具选择和真实 reasoning。
- `api-and-sse-contracts`：登记 Chat configuration、Prompt、Skill DTO、multipart policy 与七个受保护 OpenAPI operation。

## Impact

- 后端新增 Alembic revision、Prompt/Skill 领域 records/Repository/service/parser、SQLite adapter、API router 与 Agent 配置装配器，并为 YAML safe parsing 增加显式 PyYAML 依赖。
- P15 `AgentChatRunner` 与请求级 tool factory 接收动态 system prompt 和 `load_skill` Tool，但现有 knowledge/time 工具、SSE、审计及消息事务语义保持不变。
- `packages/api-contracts` 增加配置资产类型、选择请求、上传 policy 与 path；前端新增 typed client/store，不新增 P19 才交付的最终 UI。
- 新增五个 docs 示例 Skill；本机 JSON、Compose、Milvus schema 和认证 token 持久化规则不变。
