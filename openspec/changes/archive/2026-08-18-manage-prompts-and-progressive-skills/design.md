## Context

P15 已把 `create_agent`、请求级工具工厂、CurrentUser、流式事件和审计组合成持久 Chat turn。当前固定 system prompt 位于 Agent runner，尚无用户配置 Repository。P16 需要跨 contracts、SQLite、FastAPI、Agent 装配和前端 store 扩展，且必须保持 import-safety 与现有 owner scope。动机与范围见 `proposal.md`，行为合同见三个 delta specs。

## Goals / Non-Goals

**Goals:**

- 用三张 owner-scoped 表表达配置、Prompt 和 Skill，保持明确事务与可替换 Repository 边界。
- 每轮创建不可变配置快照，只把 Skill 摘要放入 system prompt，并用 owner-bound Tool 按需读取正文。
- 使上传 parser、Agent 装配、Tool loader、HTTP 和前端状态可独立注入、测试且模块 import 无 I/O。

**Non-Goals:**

- 不实现 P19 最终侧栏、资产编辑页面或浏览器内 Markdown 编辑器。
- 不建立项目级静态 Skill catalog、自动扫描 examples、Skill 版本历史、共享/市场或 MCP Skill。
- 不允许用户 Prompt 修改平台安全规则、工具实现、CurrentUser 或 tenant filter。

## Decisions

### 1. 三张表表达资产与当前选择

`user_chat_configurations` 每 owner 最多一行，保存 nullable selectedPromptId；`user_chat_prompts` 保存 label/content；`user_chat_skills` 保存解析后的标准字段、canonical metadata 与 `is_selected`。Skill 多选通过 owner 内的 `is_selected` 表达，configuration PUT 在一个事务中校验目标集合并更新全部 Skill 选择，避免为本 change 增加第四张关联表或把可查询关系塞进 JSON。

备选的单 JSON 配置无法用唯一约束、外键与 owner-scoped SQL 保证资产一致性；单独 selection join 表则偏离用户明确要求的三张表，均不采用。

### 2. 删除已选 Prompt 回退为平台规则

删除服务在同一事务里先清空当前 configuration 的 selectedPromptId，再删除 Prompt；不自动选择其他 Prompt。这样 fallback 确定、不会因剩余资产排序变化而改变下一轮行为。删除 Skill 直接移除带 `is_selected` 的资产，因此选择集合同步收缩。

### 3. 使用 PyYAML safe_load 与统一规范化 parser

后端显式依赖 `PyYAML>=6,<7`。`SkillDocumentParser` 先检查严格 filename、256 KiB 与 UTF-8，再解析 `---` YAML frontmatter。根节点必须为对象且所有值可转换为 JSON-safe 类型；name/description 走单一验证与规范化入口。API、五个示例测试和 `load_skill` 输入复用同一 name 规范化规则。

手写 YAML 子集会产生与标准 Skill 文件不兼容的边缘语义；不安全 loader 可能构造 Python 对象，因此均不采用。

### 4. 每轮配置快照固定本轮权限

`ChatAgentConfigurationService` 在 runner factory 创建前，用独立短事务按 owner 读取 Prompt 与已选 Skill，返回 frozen snapshot：userPrompt、Skill summaries 和 allowed normalized names。选择在 turn 中途变化不修改 snapshot；下一轮重新读取。

该快照既避免长事务跨模型调用，也防止 `load_skill` 在本轮运行期间因配置变更扩大白名单。Repository 与 Tool 仍在读取正文时再次带 owner scope，白名单和 owner 条件缺一不可。

### 5. 平台规则与用户内容采用显式信任分层

`SystemPromptAssembler` 以固定模板拼接：不可覆盖的平台规则、带明确边界标记的用户 Prompt、只含 name/description 的 Skill catalog。平台规则声明用户配置不能改变 tenant/tool 边界；真正的安全性继续由代码中的 CurrentUser、Repository 和 Tool filter 强制，而非依赖模型遵循文字。

不把 Skill content 交给 assembler；初始 system prompt 的测试使用正文 sentinel 证明其不存在。没有 Prompt/Skill 时仍返回平台规则，不制造空 system prompt。

### 6. load_skill 是请求级 Tool 且延迟读正文

`create_load_skill_tool` 闭包绑定 CurrentUser、allowed names 与可注入 `SkillContentLoader`。模型调用时先规范化 name、检查 snapshot allowlist，再通过独立短事务按 owner+name 读取 content；失败返回安全业务错误并进入现有 tool failed/audit/SSE 流程。它不扫描 docs examples，也不缓存跨用户正文。

生产 Agent factory 接收动态 system prompt，工具列表扩展为 knowledge、time、load_skill。现有 event mapper 继续只转发真实 reasoning，不从 Prompt 或 Skill 生成 reasoning。

### 7. HTTP 与前端保持服务器事实来源

FastAPI router 只做合同解析、CurrentUser 注入和 envelope；service 负责事务、fallback 与验证。configuration GET 返回所有当前用户资产及选择，PUT 原子替换选择。前端 `configurationClient` 复用 ApiClient，multipart 上传使用原始 FormData；Pinia store 在成功写后使用服务端 DTO/刷新对账，并注册 protected cleanup，不写 localStorage。

## Risks / Trade-offs

- [Skill content 可能增加上下文] → 初始 prompt 只放摘要，完整正文仅由模型按需加载且上传大小有界。
- [YAML 可表达非 JSON 类型] → safe_load 后执行 JSON-safe 验证，拒绝日期、二进制或自定义对象等不稳定 metadata。
- [配置更新与正在运行的 turn 竞态] → 每轮使用不可变快照；更新只影响下一轮。
- [用户 Prompt 注入攻击] → system prompt 明确信任分层，真正权限由 owner-scoped Repository 与 Tool allowlist 强制。
- [is_selected 批量更新写放大] → 当前是本地单用户、小规模资产，单事务更新换取简单且确定的一致性。
- [P15 工作树尚未整体提交] → P16 只在现有文件上增量编辑，Git 操作显式列出 P16 文件并保留无关改动。

## Migration Plan

1. 增加 PyYAML 锁文件更新、共享 contracts 与 Alembic 三表 migration；fresh SQLite 升级并验证 metadata 一致。
2. 发布 parser、Repository/service/API 和示例 Skill；旧 Chat API 不受影响。
3. 接入请求级配置快照、动态 system prompt 与 `load_skill`，保留现有 knowledge/time 工具和消息事务语义。
4. 发布前端 typed client/store；P19 再接入最终 UI。
5. 回滚应用代码时三张新表不影响 P15；数据库降级删除 P16 表，现有会话与审计保留。
