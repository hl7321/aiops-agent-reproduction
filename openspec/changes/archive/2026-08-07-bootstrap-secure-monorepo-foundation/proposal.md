## Why

项目目前只有 OpenSpec 初始化文件，尚无可安装、可运行或可验证的工程基础。首个变更必须先建立最终技术栈、目录边界、安全配置边界和统一质量门禁，避免后续认证、聊天、知识库、AIOps 与 MCP 等能力在不一致或不安全的基础上演进。

## What Changes

- 建立包含后端、前端、共享 API contracts、配置、基础设施说明、脚本、OpenSpec 和文档的最终 monorepo 目录。
- 锁定 Python/FastAPI 后端、Agent/AI 依赖边界、Vue/Vite 前端、npm workspaces、VitePress 和 Conventional Commits。
- 创建最小可运行的 FastAPI `/health` app factory、Vue 桌面 Web 页面和 typed contracts 入口。
- 建立 uv、npm 锁文件以及 Ruff、strict Pyright、pytest、Vitest、TypeScript 和构建门禁。
- 建立只读取本机 JSON 的通用配置深合并，并严格限制进入浏览器 bundle 的公开字段。
- 从第一天忽略真实配置、凭据、缓存、依赖、构建产物、SQLite 和日志，模板中的 key、secret、password 保持为空。
- 用自动化测试约束目录、包导入、脚本、ignore、import safety、配置合并和前端 public-config allowlist，并以 sentinel secret 构建扫描证明秘密不会进入 `dist`。
- 只记录未来 Compose 的基础设施边界，不实现认证、聊天、知识库、AIOps、MCP、LLM、Milvus 或其他产品功能。

## Capabilities

### New Capabilities

- `monorepo-foundation`: 定义安全 monorepo 的技术栈、目录、最小可运行骨架、配置公开边界和质量验收行为。

### Modified Capabilities

无。

## Impact

- 新增 `apps/backend`、`apps/frontend`、`packages/api-contracts`、`config`、`infra`、`scripts` 和 `docs` 工程内容。
- 更新根 `.gitignore`、`AGENTS.md`、`package.json`、npm lockfile 和 `openspec/config.yaml`。
- 引入 Python、Node.js 和文档构建依赖，但不启用数据库、LLM、Milvus、MCP 或应用容器运行时。
- 新增面向本地开发和 CI 的统一安装、类型检查、测试、构建和 OpenSpec 验证命令。
