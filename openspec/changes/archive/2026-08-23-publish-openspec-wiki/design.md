## Context

见 `proposal.md`。仓库已有 VitePress workspace 和 26 个归档 change，但当前文档站只有基础配置，没有 OpenSpec 导航、生成页面或稳定同步协议。OpenSpec artifacts 必须继续由 `openspec/` 独占，WIKI 只能形成视图；同时 P27 本身要求在 active 和 archive 两个时点被正确呈现。

## Goals / Non-Goals

**Goals:**

- 建立从 OpenSpec 目录树到 VitePress 页面、索引和 Sidebar 的确定性投影。
- 发布 P01–P27 的 change artifacts 与全部 main specs，同时保持单一事实来源。
- 把 include 完整性、归档 delta 同步状态和集合计数变成独立可执行门禁。
- 提供仓库内 `wiki-sync` skill，让后续 lifecycle 重用同一脚本而不是重新解释规则。
- 在 macOS、Linux、Git Bash 和启用 symlink 能力的 Windows checkout 中给出一致结果。

**Non-Goals:**

- 不编辑或格式化任何 OpenSpec 原 artifacts，不建立数据库或搜索索引来存储 WIKI。
- 不更改后端、前端、contracts、基础设施或任何产品 API。
- 不在 P27 运行 Qwen、Milvus、CLS MCP 或 P25 fixtures，也不把自动测试冒充真实链路验收。
- 不引入将符号链接展开为复制目录的 Windows fallback。

## Decisions

### 1. 相对符号链接加 include，拒绝正文复制

`docs/openspec` 固定为指向 `../openspec` 的相对符号链接。生成的 Markdown 只写 frontmatter、章节标题和 `<!--@include: ...-->`，include 目标从页面目录相对解析到 `docs/openspec`。这样 VitePress 构建、仓库浏览和离线审计都读取同一组源文件。

备选方案是将 artifacts 复制到 `docs` 或使用构建时临时复制。两者都会制造双事实源或让构建成功掩盖未同步内容，因此拒绝。

### 2. 单一 Python 同步器负责模型、渲染和审计

`scripts/sync_wiki.py` 使用标准库扫描 `openspec/changes`、`openspec/changes/archive` 和 `openspec/specs`，形成排序后的不可变模型，再渲染以下内容：

- `docs/changes/active/<change>/index.md`
- `docs/changes/archive/<dated-change>/index.md`
- `docs/specs/<capability>/index.md`
- `docs/changes/index.md`
- `docs/.vitepress/openspec-sidebar.generated.mts`

脚本提供 `active`、`archive`、`all` 子命令，并提供 `audit-includes`、`audit-counts` 或等价的审计入口。可选 `--date YYYY-MM-DD` 让测试和首次 active frontmatter 不依赖系统时间；已有页面的 createdDate 在后续同步中保持。所有集合排序、文本换行和序列化格式固定，重复执行不产生 diff。

备选方案是在 VitePress config 中运行任意文件系统扫描。它会把同步错误推迟到 Node 构建期，也不便于 archive 前检查 delta sync，因此采用显式 Python 工具。

### 3. VitePress 配置导入生成 Sidebar 模块

将现有最小配置迁移到 `docs/.vitepress/config.mts`，配置中文导航并导入同步器生成的 `openspec-sidebar.generated.mts`。根 `package.json` 暴露 `docs:dev`、`docs:build`、`docs:preview`，docs workspace 同步增加 preview。

脚本不以字符串替换方式改写手写 config；它只完整重建专属 generated module。这样手写站点配置和生成导航的所有权清楚，也便于测试幂等。

### 4. 归档 delta 同步采用语义级最低保证

archive 模式从目标归档 change 的 `specs/**/spec.md` 读取 delta operations，并与相同 capability 的 main spec 比较：

- ADDED/MODIFIED requirement 必须在 main spec 存在；对应 delta scenario 标题必须存在。
- REMOVED requirement 必须在 main spec 不存在。
- RENAMED 的新名称必须存在，旧名称必须不存在。

检查失败默认中止。只有显式 `--allow-unsynced` 才允许继续并打印醒目例外。该检查不替代 OpenSpec archive workflow 的智能合并，而是防止 WIKI 把未同步归档误标为完成。

备选方案是只检查 main spec 文件存在，无法发现遗漏 requirement；对所有历史正文做字节级相等又会因后续 change 合法演进产生误报，因此选择 requirement/scenario 语义检查。

### 5. 生成目录按源集合做垃圾回收

每次模式同步都会删除目标作用域中不再存在于源模型的生成页面；archive 模式还按基础 change 名删除对应 active 页面。清理只允许发生在 `docs/changes/active`、`docs/changes/archive`、`docs/specs` 的受控生成目录，不触碰手写文档或 OpenSpec 源。

P27 的执行顺序固定为：实现脚本 → active sync P27 → all sync P01–P26 与主规格 → 工程验证 → OpenSpec verify/spec sync/archive → archive sync P27 → 再次审计和构建。最终 active 集合为空，archive 集合为 27。

### 6. skill 保持短小并委托确定性脚本

`.codex/skills/wiki-sync/SKILL.md` 只包含触发条件、模式选择、安全边界和必须执行的验证；复杂规则保留在脚本及其 CLI 帮助中。skill 由 skill-creator 规范校验。由于新 skill 在创建它的当前 turn 可能尚不可发现，P27 按用户授权直接运行脚本，下一 turn 起由 `$wiki-sync` 触发。

## Risks / Trade-offs

- **[历史 delta 随后续演进而与最新 main spec 不完全一致]** → archive 审计比较 requirement/scenario 语义而非全文，并允许只有用户显式声明时使用 unsynced 例外。
- **[Windows 默认 checkout 将 symlink 物化为普通文件]** → setup 文档、脚本启动检查和 Git 配置验证都给出可操作错误；不提供复制 fallback。
- **[generated Sidebar 与页面在人工编辑后漂移]** → 文件标记为自动生成，每次同步整体重建，并通过集合计数检查识别漂移。
- **[VitePress 能构建但 include 未展开或目标断裂]** → 将 include target audit 设为独立门禁，不能以 docs build 替代。
- **[清理逻辑误删手写文件]** → 只操作三个明确的 generated 根目录，并在测试中使用临时仓库验证边界。

## Migration Plan

1. 用测试驱动建立同步模型、symlink 检查、渲染、delta sync 审计、include 审计和计数审计。
2. 创建 skill、VitePress 配置和脚本入口，在仓库内建立相对 symlink。
3. 对 P27 执行 active sync，再对 P01–P26 和 main specs 执行 all sync。
4. 运行完整自动门禁并完成 OpenSpec verify；同步 P27 delta 到 main spec 后归档。
5. 对 P27 执行 archive sync，重新运行 OpenSpec、include、docs build 和计数审计，最后提交 Git。

回滚时可以删除生成页面、generated Sidebar、skill 和 symlink，并恢复原 VitePress 配置；OpenSpec 原 artifacts 始终未被修改，因此不存在内容迁移回滚。
