# 智能 OnCall Agent WIKI

这里发布项目当前的工程文档、全部 OpenSpec 主规格和 change 历史。OpenSpec 正文始终保存在仓库 `openspec/`，WIKI 页面通过 include 引用它们，不维护第二份副本。

## 导航

- [OpenSpec 变更总览](./changes/)
- [主规格](./specs/)
- [运行与监控](./operations-and-monitoring.md)
- [真实日志与告警教程](./tutorials/real-log-and-alert.md)

## 验证入口

请从仓库根目录运行：

```bash
uv run --project apps/backend python scripts/sync_wiki.py audit-includes
uv run --project apps/backend python scripts/sync_wiki.py audit-counts
npm run docs:build
```

文档构建成功不能替代 include target audit；完整工程门禁见根 README 与 `AGENTS.md`。
