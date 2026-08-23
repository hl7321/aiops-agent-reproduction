## 1. 同步器测试与核心模型

- [x] 1.1 先为 active/archive/all、稳定排序、日期保持和受控垃圾回收编写临时仓库测试
- [x] 1.2 实现 `scripts/sync_wiki.py` 的仓库扫描、页面模型、确定性渲染和 CLI 模式
- [x] 1.3 为相对 symlink 检查、错误目标、普通目录和 Windows 可操作提示编写并通过测试

## 2. 规格同步与完整性审计

- [x] 2.1 先为 ADDED/MODIFIED/REMOVED/RENAMED delta 同步判断及显式 unsynced 例外编写测试
- [x] 2.2 实现 archive delta sync 审计，默认拒绝缺失 delta 或未同步 main spec
- [x] 2.3 先为 include 缺失、路径越界、集合遗漏/重复和计数一致性编写测试
- [x] 2.4 实现独立 include target audit 与 changes/specs/index/Sidebar 集合计数审计

## 3. VitePress WIKI 与 skill

- [x] 3.1 建立 `docs/openspec -> ../openspec` 相对符号链接，迁移中文 `config.mts` 并接入生成 Sidebar
- [x] 3.2 为根和 docs workspace 增加 docs:dev/docs:build/docs:preview，并更新中文 WIKI 入口
- [x] 3.3 使用 skill-creator 规范创建 `.codex/skills/wiki-sync/SKILL.md`，运行 skill quick validation
- [x] 3.4 更新 AGENTS、README 与 Windows setup，固化后续 lifecycle 同步规则和 symlink 故障处理

## 4. 初始同步与 P27 active 验证

- [x] 4.1 运行 active sync 生成 P27 页面，再运行 all sync 发布 P01–P26、全部 main specs、索引和 Sidebar
- [x] 4.2 执行 include audit、计数审计、脚本单测/语法检查和 `npm run docs:build`
- [x] 4.3 确认生成页面只含 frontmatter/导航/include，OpenSpec 原 artifacts 除 P27 规划文件外没有被同步器修改

## 5. 全平台门禁与 OpenSpec 验证

- [x] 5.1 运行 `openspec validate --all`、contracts typecheck/test、backend Alembic/Ruff/Pyright/pytest
- [x] 5.2 运行 frontend typecheck/test/build、docs build、Compose config、启动脚本语法和 `git diff --check`
- [x] 5.3 使用 `$openspec-verify-change` 核对 completeness/correctness/coherence，修复全部 CRITICAL 并处理 WARNING

## 6. 归档后外部收尾

以下步骤发生在 change 已通过 verify 并移出 active 目录之后，不属于归档前 implementation task 计数，但仍是 P27 完整生命周期的强制收尾：

- 将 P27 delta spec 同步到 main spec，确认语义一致后归档 P27。
- 当前 turn 无法发现新 `$wiki-sync` 时，直接运行 `sync_wiki.py archive`，清理 P27 幽灵 active 页面。
- 归档后再次运行 OpenSpec、include audit、docs build、计数和 diff 门禁，确认 27 个唯一归档 change、全部 main specs、零 active 重复。
- 使用 Conventional Commit 提交并保存 P27 完整结果。
