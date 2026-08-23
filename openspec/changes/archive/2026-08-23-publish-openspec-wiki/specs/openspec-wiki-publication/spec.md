## Purpose

为项目提供以 OpenSpec 原始 artifacts 和主规格为唯一事实来源的可导航中文 WIKI，并通过确定性同步、符号链接检查与独立 include 审计保证创建、归档和发布过程无遗漏、无断链、无重复副本。

## ADDED Requirements

### Requirement: WIKI 必须以 OpenSpec 为唯一事实来源
系统 MUST 通过 `docs/openspec` 到仓库 `openspec` 的相对符号链接访问规格，并 MUST 使用 VitePress include 引用 proposal、design、tasks、delta specs 与主规格正文；系统 MUST NOT 把这些正文复制到生成页面。

#### Scenario: 构建归档变更页面
- **WHEN** 同步器为一个包含完整 artifacts 的归档 change 生成 WIKI 页面
- **THEN** 页面只包含统一元数据、导航结构和指向归档目录原文件的 include 指令

#### Scenario: 符号链接被普通目录替代
- **WHEN** `docs/openspec` 不存在、不是符号链接或指向错误目标
- **THEN** 同步或审计 MUST 失败并输出可操作的修复提示，且 MUST NOT 静默复制 `openspec` 目录

### Requirement: 同步器必须支持确定性的生命周期模式
系统 MUST 提供 `active`、`archive`、`all` 三种同步模式；相同仓库状态和显式日期输入 MUST 生成相同页面、索引与 Sidebar，并 MUST 清理不再有效的生成条目。

#### Scenario: 创建 active change 后同步
- **WHEN** 使用 `active` 模式同步当前 change
- **THEN** 系统生成 `docs/changes/active/{change}/index.md`，写入 title、status、createdDate，并把它加入索引和 Sidebar

#### Scenario: change 归档后同步
- **WHEN** 使用 `archive` 模式同步已经归档的 change
- **THEN** 系统生成 `docs/changes/archive/{date}-{change}/index.md`，写入 title、status、createdDate、archivedDate，引用归档路径，并删除同名幽灵 active 页面和导航条目

#### Scenario: 全量同步
- **WHEN** 使用 `all` 模式同步仓库
- **THEN** 系统按稳定排序同步全部 active changes、archive changes、main specs、总索引和 Sidebar

### Requirement: 归档同步必须验证 delta specs 已同步
系统 MUST 在 archive 模式发布 change 前确认 delta specs 存在并已经反映到对应 main specs；未同步时 MUST 默认拒绝，只有调用者显式声明允许 unsynced 才可继续。

#### Scenario: delta specs 尚未同步
- **WHEN** archive 模式发现新增或修改的 requirement 未出现在对应 main spec
- **THEN** 同步 MUST 以非零状态退出，说明差异，且不得生成误导性的归档 WIKI 页面

#### Scenario: 显式允许未同步归档
- **WHEN** 调用者明确传入允许 unsynced 的选项
- **THEN** 系统可生成归档页面，但 MUST 明确报告该例外，不能把它当作默认行为

### Requirement: include 目标必须独立审计
系统 MUST 提供独立于 VitePress 构建的 include target 审计，遍历所有生成页面并验证每个 include 路径存在、位于仓库允许范围内且可读取。

#### Scenario: docs build 成功但 include 目标缺失
- **WHEN** VitePress 构建返回成功而任一 include 指向不存在的文件
- **THEN** 独立审计 MUST 失败并报告页面与缺失目标，整体 WIKI 门禁 MUST 判定失败

#### Scenario: 所有 include 有效
- **WHEN** 每个生成页面的 include 都可解析到现存 OpenSpec 文件
- **THEN** 审计返回成功并报告已检查页面和目标数量

### Requirement: WIKI 必须完整且可计数
系统 MUST 生成中文首页、变更总索引、active/archive 导航、主规格导航和 Sidebar；同步后 MUST 能对 OpenSpec changes、main specs、索引条目、Sidebar 条目和页面进行一一计数，且不得存在 active/archive 重复。

#### Scenario: P27 最终归档同步
- **WHEN** P01–P27 全部归档且 P27 archive 同步完成
- **THEN** WIKI 包含 27 个唯一归档 change、零个 P27 active 条目、全部 main specs，并且索引、Sidebar 与页面计数一致

#### Scenario: 发生遗漏或重复
- **WHEN** change 页面、索引、Sidebar 或 OpenSpec 源目录之间的标识集合不一致
- **THEN** 计数审计 MUST 失败并列出缺失、额外或重复标识

### Requirement: Windows 必须显式保障符号链接能力
Windows 操作文档 MUST 要求启用 Developer Mode 或具备创建 symlink 的权限，并启用 Git symlink 支持；用户 MUST 能验证 checkout 后 `docs/openspec` 仍是链接。

#### Scenario: Windows checkout 不保留符号链接
- **WHEN** Windows 用户检出仓库后 `docs/openspec` 变成普通文件或目录
- **THEN** 文档和同步器 MUST 提供检查 Git 配置、Developer Mode、重新检出的具体提示，而不是复制一份 OpenSpec 内容

### Requirement: 后续 OpenSpec 生命周期必须同步 WIKI
仓库 MUST 提供可发现的 `wiki-sync` skill，指导后续 change 创建后执行 active 同步、归档后执行 archive 同步，并在完成前运行 include 与计数审计。

#### Scenario: skill 执行 active 同步
- **WHEN** 用户要求同步新创建或更新的 active change
- **THEN** skill 调用确定性同步器的 active 模式并验证生成页面与 include 目标

#### Scenario: skill 执行 archive 同步
- **WHEN** 用户要求同步刚归档的 change
- **THEN** skill 调用 archive 模式、强制检查 delta 同步状态、清理 active 条目并验证最终计数
