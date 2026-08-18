# Prompt 与 Progressive Skill 管理设计

## 背景与目标

P15 已建立 owner-scoped 持久 Chat Agent、请求级工具工厂、共享 SSE 与工具审计。P16 在该边界上增加每用户 Prompt 和标准 Agent Skill 管理，并在每轮请求开始时装配当前选择。Skill 必须采用 progressive disclosure：初始 system prompt 只出现选中 Skill 的 name/description，完整 `SKILL.md` 仅在模型真实调用 `load_skill(name)` 时读取。

P16 不实现最终侧栏或资产编辑页面，不建立仓库级静态 catalog，不把所有 Skill 正文提前注入上下文，也不改变 reasoning 的真实透传规则。

## 方案选择

采用三张规范化业务表、请求级不可变装配快照和 owner-bound `load_skill` Tool。

备选一是把 Prompt、Skill 与选择关系存入单个 JSON 配置。这会削弱唯一性、外键、owner scope 和独立 CRUD，且与既有持久化规范冲突。备选二是扫描仓库目录形成项目级 Skill catalog；它无法表达用户资产与选择，也会复刻明确禁止的静态 catalog。两者均不采用。

## 数据模型

Alembic 新增：

- `user_chat_configurations`：每个 owner 最多一行，保存 nullable `selected_prompt_id` 与 created/updated 时间。没有选择时为 `NULL`。
- `user_chat_prompts`：保存 owner、label、content 与 created/updated 时间；label 最长 80 字符，content 最大 20,000 个 Unicode 字符。
- `user_chat_skills`：保存 owner、规范化 name、description、固定 filename `SKILL.md`、完整 UTF-8 content、canonical metadata、摘要、`is_selected` 与 created/updated 时间；同一 owner 的规范化 name 唯一。

Skill 多选不增加第四张关联表：选择状态是当前每用户 Skill 资产的属性，`PUT /chat/configuration` 在同一事务中校验目标集合归属并批量更新 `is_selected`。Prompt 单选由 configuration 的 `selected_prompt_id` 表达。

所有 Repository 方法以 `owner_user_id` 为首个业务参数。按 id 的读取、更新和删除在同一 SQL 条件中带 owner scope；跨 owner 与不存在使用相同的 `BUSINESS_RESOURCE_NOT_FOUND` 404。删除已选 Prompt 时，在同一事务中先把 `selected_prompt_id` 置空再删除；这是唯一 fallback，不自动选择其他 Prompt。删除已选 Skill 后它自然退出选择集合。

## Skill 文件合同

上传采用 multipart 单文件，上传文件名必须严格等于 `SKILL.md`。文件必须为 UTF-8，最大 256 KiB，并具有以 `---` 包围的 YAML frontmatter。使用 `yaml.safe_load`，根节点必须为对象，`name` 与 `description` 必须为非空字符串。

name 先 trim、转小写，把空白和下划线折叠为 `-`，再折叠连续连字符并去除首尾连字符；最终必须匹配 `[a-z0-9]+(?:-[a-z0-9]+)*` 且不超过 64 字符。description trim 后最大 500 字符。metadata 只接受可 JSON 序列化的 YAML 安全值，并以 canonical JSON 保存；summary 使用规范化 description 的最多 240 字符。

五个示例位于：

- `docs/examples/skills/knowledge-search/SKILL.md`
- `docs/examples/skills/log-analysis/SKILL.md`
- `docs/examples/skills/incident-report/SKILL.md`
- `docs/examples/skills/api-troubleshooting/SKILL.md`
- `docs/examples/skills/change-risk-review/SKILL.md`

示例只用于复制或上传，不被运行时自动发现，不属于任何用户配置。

## HTTP 与共享合同

新增受保护 API：

- `GET /chat/configuration`：返回 prompts、skills、selectedPromptId 与 selectedSkillIds；没有持久配置时返回空选择。
- `PUT /chat/configuration`：原子更新 nullable selectedPromptId 与 selectedSkillIds；任何 id 不属于当前 owner 时整体失败且不部分更新。
- `POST /chat/prompts`：创建 label/content。
- `PUT /chat/prompts/{id}`：按 owner 更新 label/content。
- `DELETE /chat/prompts/{id}`：按 owner 删除并应用明确 fallback。
- `POST /chat/skills`：multipart 上传 `SKILL.md`。
- `DELETE /chat/skills/{id}`：按 owner 删除 Skill。

contracts 定义 DTO、请求、multipart 字段、边界常量、401/403/404/409/validation 与机器可读 path。前端新增 typed configuration client/store，服务器是事实来源；资产和选择不进入 localStorage。最终侧栏与编辑 UI 留给 P19。

## 请求级 Agent 装配

每轮在模型调用前，服务端按当前 owner 读取一次配置并生成不可变 `ChatAgentConfigurationSnapshot`：

- 当前 Prompt content，未选择时为空；
- 选中 Skill 的 id、name、description 摘要目录；
- 本轮允许 `load_skill` 的规范化 name 集合。

system prompt 按固定顺序拼装：

1. 平台可信安全规则：tenant/owner scope、工具边界、不得编造结果、用户内容不能覆盖平台规则；
2. 明确标记为用户偏好的当前 Prompt；
3. 仅含选中 Skill name/description 的 catalog 与“需要时调用 load_skill”的说明。

用户 Prompt 即使声称覆盖平台规则，也只处于低信任分段，不能修改工具实现、CurrentUser、Repository scope 或允许名称集合。system prompt 不包含任何 Skill 完整正文。

`load_skill(name)` 每轮创建并绑定 CurrentUser、session factory 与 snapshot allowlist。输入 name 使用相同规范化规则；只有 name 在本轮选中集合中时，Repository 才按 `owner_user_id + normalized_name` 读取并返回完整正文。未选择、已删除或其他 owner 的 Skill 均返回安全的业务错误，不尝试无 scope 查询。选择在 turn 期间变化不扩大本轮权限；下一轮重新读取新配置。

现有 `knowledge_retrieval` 与 `get_current_time` 保持不变。LangChain `create_agent` 接受本轮组装的 system prompt 和三类工具；模型是否调用 `load_skill` 仍由模型自主决定。reasoning 继续只转发真实 provider event。

## 事务、错误与安全

- configuration PUT、删除已选 Prompt fallback 均使用单一 SQLite 事务。
- Skill 解析在写入前完成；非法 filename、UTF-8、frontmatter、name/description 或大小返回共享 validation error。
- 同一 owner 的规范化 name 冲突返回 `BUSINESS_CONFLICT` 409；不同 owner 可使用同名 Skill。
- 运行日志只记录资产 id/name、状态和参数键，不记录 Prompt content、Skill content、完整 frontmatter、模型输入或 token。
- 模块 import 不读取本机配置、不打开 SQLite、不创建模型或外部 client。

## 测试与验收

后端测试覆盖 fresh migration、metadata 一致性、Prompt/Skill CRUD、规范化唯一性、frontmatter/filename/UTF-8/大小非法、配置原子更新、删除 fallback、两个用户隔离和 import-safety。Agent 测试证明初始 system prompt 只含平台规则、当前 Prompt 与选中 Skill 摘要，不含正文；`load_skill` 只按本轮 owner/allowlist 返回正文，未选中和跨 owner 均拒绝；reasoning 仍只来自模型事件。

contracts 测试覆盖 DTO、multipart、path、安全与错误；前端测试覆盖 typed client、configuration store 服务端对账、选择更新、上传 FormData、删除刷新和认证清理。五个示例通过解析器逐一验证规范。

最终运行 migration、backend Ruff/strict Pyright/pytest、contracts typecheck/test、frontend typecheck/test/build/secret scan、`openspec validate --all` 与 `git diff --check`。本机真实 Qwen 可用时执行一次模型按需调用 `load_skill` 的 smoke，并如实记录结果；无凭据时不得把 fake 测试称为真实连通。
