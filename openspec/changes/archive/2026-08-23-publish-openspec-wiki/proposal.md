## Why

P01–P26 已形成完整的 OpenSpec 历史和主规格，但这些权威资料仍分散在仓库目录中，缺少可导航、可构建且不会产生第二事实源的中文 WIKI。P27 在平台交付收尾阶段建立确定性同步机制，使后续 change 的创建、归档和规格演进都能稳定反映到 VitePress 文档站。

## What Changes

- 使用 VitePress 发布所有 OpenSpec 主规格、active change 与 archive change，并通过 `<!--@include: ...-->` 引用原始 artifacts，禁止复制正文。
- 建立 `docs/openspec` 到仓库 `openspec` 的相对符号链接，并为 Windows symlink 能力提供明确检查与故障提示。
- 为变更页面建立统一 frontmatter、中文导航、索引和 Sidebar，覆盖 proposal、design、tasks 与 delta specs。
- 新增确定性的 `scripts/sync_wiki.py`，支持 `active`、`archive`、`all` 三种模式，校验 include 目标、delta spec 存在性与同步状态，并清理幽灵 active 页面。
- 新增仓库内 `.codex/skills/wiki-sync/SKILL.md`，要求后续 OpenSpec change 创建和归档时同步 WIKI。
- 对 P01–P26 全部归档资料和全部主规格执行初始同步；P27 自身先同步 active，归档后再同步 archive 并执行计数与断链审计。
- 扩展根文档脚本，提供 `docs:dev`、`docs:build`、`docs:preview`，并把 WIKI 审计纳入最终交付门禁。

## Capabilities

### New Capabilities

- `openspec-wiki-publication`: 定义 OpenSpec artifacts 与主规格的单一事实源发布、确定性同步、符号链接兼容、include 审计和完整性计数行为。

### Modified Capabilities

- 无。

## Impact

- 影响根 `package.json`、`docs` VitePress 配置与生成页面、`scripts/sync_wiki.py`、`.codex/skills/wiki-sync`、相关自动化测试和项目协作说明。
- 不修改任何既有 OpenSpec artifact 正文，不改变后端、前端、数据库、模型、Milvus、MCP 或 AIOps 运行时行为。
- 自动门禁不依赖真实 Qwen、Milvus 或 CLS 凭据，也不触发 P25 外部副作用；真实桌面全链路仍作为代码冻结后的独立人工发布验收。
