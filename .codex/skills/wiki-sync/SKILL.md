---
name: wiki-sync
description: 同步本仓库 OpenSpec active/archive changes 与主规格到 VitePress WIKI；在 change 创建、更新、归档或需要审计 WIKI 完整性时使用。
---

# OpenSpec WIKI 同步

从仓库根目录运行确定性同步器，保持 `openspec/` 为唯一事实来源。

## 模式选择

- change 仍位于 `openspec/changes/<change>` 时，运行 `uv run --project apps/backend python scripts/sync_wiki.py active`。
- change 已归档时，运行 `uv run --project apps/backend python scripts/sync_wiki.py archive --change <change-name>`。
- 需要重建所有 active、archive、main specs、索引和 Sidebar 时，运行 `uv run --project apps/backend python scripts/sync_wiki.py all`。

archive 模式必须在 delta specs 已同步到 main specs 后运行。只有用户明确要求接受未同步归档时，才可添加 `--allow-unsynced`；不要自行放宽。

## 完成条件

同步后始终运行：

```bash
uv run --project apps/backend python scripts/sync_wiki.py audit-includes
uv run --project apps/backend python scripts/sync_wiki.py audit-counts
npm run docs:build
```

若 `docs/openspec` 不是指向 `../openspec` 的相对符号链接，按脚本提示修复 checkout；禁止复制 artifacts 到 `docs`。不要编辑 OpenSpec 原 artifacts 来修复生成页问题，应修复同步器或完成正确的 spec sync。
