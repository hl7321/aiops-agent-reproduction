## Purpose

本能力为每个用户提供服务端持久化的 Chat Prompt 与标准 Agent Skill 资产、选择配置和安全的 progressive disclosure，使模型只在真实需要时加载当前用户已选 Skill 的完整正文。

## ADDED Requirements

### Requirement: Prompt 与 Skill 资产由服务端按 owner 管理
系统 SHALL 通过 SQLite 持久化每个用户的 Chat configuration、Prompt 与 Skill，并把服务端作为资产和选择状态的唯一事实来源。Prompt SHALL 保存 label 与 content；Skill SHALL 保存规范化 name、description、固定 filename、完整 content、metadata、summary 与选择状态。所有 list/create/update/delete/select/load 操作 MUST 显式限定当前 owner。

#### Scenario: 当前用户管理 Prompt
- **WHEN** 已认证用户创建或更新有效的 Prompt label/content
- **THEN** 系统只在该用户 scope 内持久化并通过 configuration API 返回最新资产

#### Scenario: 当前用户管理 Skill
- **WHEN** 已认证用户上传或删除有效 Skill
- **THEN** 系统只修改该用户的 Skill 资产与选择状态，不影响其他用户

#### Scenario: 跨用户操作资产 id
- **WHEN** 用户 B 更新、删除或选择用户 A 的 Prompt/Skill id
- **THEN** 系统返回与资源不存在相同的安全错误，不泄漏用户 A 的资产字段

### Requirement: Chat configuration 使用 Prompt 单选和 Skill 多选
系统 SHALL 提供 `GET /chat/configuration` 返回 prompts、skills、nullable selectedPromptId 与 selectedSkillIds，并提供 `PUT /chat/configuration` 原子更新当前 owner 的选择。selectedPromptId MUST 为当前 owner 的 Prompt 或 null；selectedSkillIds MUST 去重且全部属于当前 owner，任一非法 id MUST 使整个更新失败而不产生部分选择。

#### Scenario: 更新一个 Prompt 与多个 Skill
- **WHEN** 当前用户提交一个自己的 Prompt id 和多个自己的 Skill id
- **THEN** 再次读取 configuration 时获得完全相同的单选 Prompt 与去重 Skill 集合

#### Scenario: 配置包含外部资产
- **WHEN** PUT 同时包含当前用户资产和其他用户或不存在的 id
- **THEN** 系统拒绝整个更新，原 selectedPromptId/selectedSkillIds 保持不变

#### Scenario: 首次读取空配置
- **WHEN** 用户尚未创建或选择任何 Prompt/Skill
- **THEN** GET 返回空资产集合、selectedPromptId=null 与 selectedSkillIds=[]

### Requirement: 删除当前 Prompt 采用确定 fallback
系统 SHALL 在同一事务中删除当前 owner 的 Prompt；若被删除 Prompt 正是 selectedPromptId，系统 MUST 把 selectedPromptId 置为 null，且 MUST NOT 自动选择其他 Prompt。删除已选 Skill MUST 同时使它从 selectedSkillIds 消失。

#### Scenario: 删除当前选中 Prompt
- **WHEN** 用户删除 configuration 当前选中的 Prompt
- **THEN** 删除成功，selectedPromptId 变为 null，下一轮不注入其他用户 Prompt

#### Scenario: 删除未选中 Prompt
- **WHEN** 用户删除不是当前选择的 Prompt
- **THEN** 当前 selectedPromptId 保持不变

#### Scenario: 删除已选 Skill
- **WHEN** 用户删除 selectedSkillIds 中的 Skill
- **THEN** 删除成功且后续 configuration 与 Agent 请求均不再包含该 Skill

### Requirement: Skill 上传遵守标准 SKILL.md 合同
系统 SHALL 只接受 multipart 上传的 UTF-8 文件，文件名 MUST 严格等于 `SKILL.md`，大小 MUST 不超过 256 KiB。文件 MUST 包含 YAML frontmatter 对象及非空 name、description；name MUST 规范化为最多 64 字符的 lowercase kebab-case，description MUST trim 且不超过 500 字符，metadata MUST 为可 JSON 序列化的安全 YAML 值。同一 owner 的规范化 name MUST 唯一。

#### Scenario: 上传合法 Skill
- **WHEN** 用户上传带有效 frontmatter 与正文的 `SKILL.md`
- **THEN** 系统保存固定 filename、完整 content、规范化 name、metadata 与最多 240 字符的 summary

#### Scenario: name 需要规范化
- **WHEN** frontmatter name 包含大写、空格或下划线但可规范化为合法 kebab-case
- **THEN** 系统使用规范化 name 执行存储、选择和同用户唯一性检查

#### Scenario: 文件路径或 frontmatter 非法
- **WHEN** filename 不是严格的 `SKILL.md`，或文件不是 UTF-8，或 frontmatter/name/description/metadata 不合法，或文件超限
- **THEN** 系统返回共享 validation error 且不创建 Skill

#### Scenario: 同用户规范化名称冲突
- **WHEN** 同一 owner 上传另一个会规范化为已有 name 的 Skill
- **THEN** 系统返回 `BUSINESS_CONFLICT` 409，不覆盖已有 Skill

#### Scenario: 不同用户上传同名 Skill
- **WHEN** 两个 owner 分别上传相同规范化 name 的合法 Skill
- **THEN** 两份资产分别保存并只对各自 owner 可见

### Requirement: system prompt 只装配可信规则、当前 Prompt 与 Skill 摘要
每轮 Chat Agent 请求 SHALL 从服务端读取当前 owner 的选择，并按平台安全规则、当前用户 Prompt、选中 Skill catalog 的顺序组装 system prompt。Skill catalog MUST 只包含选中 Skill 的 name 与 description，MUST NOT 包含完整正文。用户 Prompt MUST 被视为低于平台规则的用户偏好，不能扩大 tenant scope、替换可信工具实现或绕过安全边界。

#### Scenario: 选中 Prompt 与两个 Skill
- **WHEN** 用户选择一个 Prompt 和两个 Skill 后发起新一轮对话
- **THEN** 本轮 system prompt 包含平台规则、该 Prompt 与两个 name/description，且不包含任一 Skill 正文

#### Scenario: 用户 Prompt 请求绕过安全规则
- **WHEN** 当前 Prompt 声称允许跨用户访问或要求忽略平台工具边界
- **THEN** Agent 仍使用 CurrentUser 绑定的 Repository/Tool scope，不能扩大权限

#### Scenario: 配置在轮次之间变化
- **WHEN** 用户在两轮之间更新 Prompt 或 Skill 选择
- **THEN** 下一轮读取新配置，而已经开始的轮次不因中途变化扩大允许 Skill 集合

### Requirement: load_skill 只按需加载本轮已选正文
系统 SHALL 为每个当前请求创建 owner-scoped `load_skill(name)` LangChain Tool。只有模型真实调用且规范化 name 同时属于本轮选择白名单与当前 owner 时，工具才返回该 Skill 完整正文；未选择、已删除、其他 owner 或不存在的 Skill MUST 安全拒绝。系统 MUST NOT 在 Agent 执行前主动调用该工具或预加载全部正文。

#### Scenario: 模型按需加载已选 Skill
- **WHEN** 模型判断需要某个已选 Skill 并调用 `load_skill(name)`
- **THEN** 工具按当前 owner 返回该 Skill 完整 content，并产生真实工具生命周期与审计

#### Scenario: 模型不调用 load_skill
- **WHEN** 模型仅凭摘要或其他工具即可回答
- **THEN** 系统不读取 Skill 完整正文，也不生成虚假 load_skill 事件

#### Scenario: 加载未选中或其他用户 Skill
- **WHEN** 模型请求的 name 不在本轮选中白名单，或只存在于其他 owner
- **THEN** 工具返回安全明确错误，不执行无 scope 查询且不返回正文

### Requirement: 前端 configuration store 只与服务端对账
前端 SHALL 提供 typed configuration client/store，支持读取与更新选择、创建/更新/删除 Prompt、multipart 上传/删除 Skill，并在每次成功写操作后以服务端响应或重新读取结果对账。Prompt、Skill 与选择状态 MUST NOT 保存到 localStorage；认证失效或 logout MUST 清除内存中的 owner 数据。P16 MUST NOT 声称最终侧栏或资产编辑页面已经完成。

#### Scenario: configuration store 初始化
- **WHEN** 已认证前端初始化配置状态
- **THEN** store 携带 bearer 调用真实 GET API，并保存服务端返回的资产与选择

#### Scenario: 上传 Skill
- **WHEN** store 上传浏览器 File
- **THEN** client 使用共享 multipart 字段发送原始文件，并以服务端 DTO 更新状态

#### Scenario: 认证失效清理
- **WHEN** configuration API 返回 401 或用户 logout
- **THEN** store 清除 prompts、skills 和选择，不请求删除服务端数据

### Requirement: 仓库提供五个规范示例 Skill
仓库 SHALL 在 `docs/examples/skills/<name>/SKILL.md` 提供 knowledge-search、log-analysis、incident-report、api-troubleshooting、change-risk-review 五个示例。每个示例 MUST 通过与上传相同的 filename、UTF-8、frontmatter、name/description 与规范化校验，且运行时 MUST NOT 自动把示例注册到用户 catalog。

#### Scenario: 验证示例目录
- **WHEN** 仓库测试遍历五个固定示例路径
- **THEN** 每个文件均可由生产 Skill parser 成功解析，目录名与规范化 name 一致

#### Scenario: 新用户读取 configuration
- **WHEN** 新用户从未上传 Skill
- **THEN** 即使仓库存在五个示例，其 skills 仍为空
