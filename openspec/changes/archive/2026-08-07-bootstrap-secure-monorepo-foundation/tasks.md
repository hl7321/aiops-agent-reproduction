## 1. 项目契约与目录

- [x] 1.1 更新 `openspec/config.yaml`，以简体中文记录完整技术栈、spec-driven 工作流和工程约束
- [x] 1.2 创建根 `AGENTS.md`，固化目录、命令、Python import/依赖注入、配置/凭据、tenant、真实 MCP、OpenSpec 简中和桌面 Web 验收规则
- [x] 1.3 创建最终目录、根中文 README、各 workspace 中文 README、基础设施与脚本边界说明

## 2. 根 workspace 与共享 contracts

- [x] 2.1 先编写 contracts 类型测试，再创建根 npm workspaces、统一 scripts 和最小 typed entrypoint
- [x] 2.2 创建 VitePress 文档 workspace 和最小中文首页
- [x] 2.3 在根目录运行 `npm install`，生成并保留真实 `package-lock.json`
- [x] 2.4 运行 contracts typecheck/test 并修复至通过

## 3. 后端基础

- [x] 3.1 先编写 health、JSON 深合并、包导入和 import-safety 测试
- [x] 3.2 创建 backend `pyproject.toml`，锁定 Python、运行依赖、Agent/AI 依赖边界及 pytest/Ruff/strict Pyright 配置
- [x] 3.3 在 `apps/backend` 运行 `uv sync`，生成并保留真实 `uv.lock`
- [x] 3.4 在 `apps/backend/src/super_ai` 实现纯函数配置加载和最小 `/health` app factory
- [x] 3.5 运行后端 Ruff、Pyright、pytest 并修复至通过

## 4. 安全配置边界

- [x] 4.1 先编写模板空凭据、ignore pattern 和递归深合并策略测试
- [x] 4.2 创建两份 JSON 模板，确保所有 key、secret、password 为空，并复制 ignored 的空本机配置供开发构建
- [x] 4.3 扩展 `.gitignore` 以覆盖真实配置、`.env*`、IDE、虚拟环境、依赖、构建产物、覆盖率、缓存、后端 var、SQLite 和日志
- [x] 4.4 验证真实本机配置被忽略且未进入暂存区

## 5. 前端桌面 Web 与公开配置

- [x] 5.1 先编写前端配置深合并、public allowlist 和 sentinel 排除测试
- [x] 5.2 创建 Vue 3.5、Vite 6、TypeScript 5.6 strict、Pinia 3、Vue Router 4、Vitest 2 的最小桌面 Web 骨架
- [x] 5.3 实现构建侧 JSON 深合并与 public-config 投影，浏览器只获得 title、apiBaseUrl 和 public analytics key
- [x] 5.4 实现临时配置 sentinel 构建扫描脚本，证明服务端 secret 不存在于 `dist`
- [x] 5.5 运行前端 typecheck/test/build 和 sentinel 扫描并修复至通过

## 6. 仓库策略与基础设施边界

- [x] 6.1 编写目录、包导入、根 scripts、禁止文件和 README 准确性测试
- [x] 6.2 明确未来 Compose 只托管 etcd、MinIO、Milvus、Attu、Alertmanager，应用和官方 CLS MCP Server 在主机运行
- [x] 6.3 验证不存在 `app.Dockerfile`、`project.compose.json`、应用 Compose 服务和 `from src.super_ai` 导入

## 7. 验证与收尾

- [x] 7.1 运行 `openspec validate --all` 并修复至通过
- [x] 7.2 运行 backend 的 Ruff、Pyright、pytest 全部门禁并修复至通过
- [x] 7.3 运行 contracts typecheck/test 与 frontend typecheck/test/build/sentinel 全部门禁并修复至通过
- [x] 7.4 运行 `git diff --check`、检查 Git ignore/staging 边界，并修复至通过
- [x] 7.5 将所有已完成任务标记为完成，重新运行完整验收后同步 delta specs 并归档 change
