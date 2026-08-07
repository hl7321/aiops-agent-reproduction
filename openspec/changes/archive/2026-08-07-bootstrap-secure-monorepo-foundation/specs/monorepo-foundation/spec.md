## Purpose

本能力为后续智能 OnCall Agent 功能提供可安装、可运行、可验证且默认保护服务端秘密的统一 monorepo 工程基础。

## ADDED Requirements

### Requirement: 仓库提供最终工程边界
仓库 SHALL 提供 `apps/backend`、`apps/frontend`、`packages/api-contracts`、`config`、`infra`、`scripts`、`openspec` 和 `docs` 目录，并通过根 workspace 命令统一调用 contracts、frontend 和 docs 的质量任务。

#### Scenario: 开发者检出基础仓库
- **WHEN** 开发者检出并安装本变更后的仓库
- **THEN** 所有最终目录均存在，且根命令能够定位相应 workspace 的脚本

### Requirement: 后端提供最小且导入安全的应用
后端 SHALL 提供可显式创建的应用和 `/health` 健康检查，且导入后端模块期间 MUST NOT 连接 SQLite、Milvus、LLM 或 MCP。项目内 Python 导入 MUST 使用 `super_ai` 包路径，不得使用 `src.super_ai`。

#### Scenario: 调用健康检查
- **WHEN** 测试通过 app factory 创建后端应用并请求 `/health`
- **THEN** 响应成功且返回稳定的 `{"status":"ok"}` 结果

#### Scenario: 仅导入后端包
- **WHEN** Python 进程导入 `super_ai` 及其应用模块
- **THEN** 导入完成且没有建立任何外部服务或数据库连接

### Requirement: 项目配置使用本地 JSON 递归深合并
应用 SHALL 先读取 `config/project.json`，再用 `config/user.project.json` 对对象字段进行递归深合并；数组和标量由用户配置覆盖。项目配置 MUST NOT 从 OS 环境变量读取。

#### Scenario: 用户只覆盖嵌套标题
- **WHEN** 项目配置同时包含标题和 API 地址，而用户配置只覆盖标题
- **THEN** 合并结果使用用户标题并保留项目配置的 API 地址

#### Scenario: 测试注入临时配置
- **WHEN** 测试向配置加载器传入临时 JSON 路径
- **THEN** 加载器只读取这些显式路径且不依赖开发者本机真实值

### Requirement: 浏览器配置遵守公开 allowlist
前端构建 SHALL 只向浏览器注入 `frontend.title`、`frontend.apiBaseUrl` 和明确标记为 public 的 analytics key。LLM、CLS、MCP、MinIO 的 key、secret 或 password MUST NOT 进入浏览器 bundle。

#### Scenario: 构建配置包含 sentinel secret
- **WHEN** 临时服务端配置包含唯一 sentinel secret 并执行前端生产构建
- **THEN** 构建成功，且递归扫描 `dist` 不得找到该 sentinel

#### Scenario: 浏览器读取公开配置
- **WHEN** 前端启动并读取构建注入配置
- **THEN** 只能获得 allowlist 中的 typed 字段，不能访问完整项目 JSON

### Requirement: 敏感本机文件默认不受 Git 追踪
仓库 SHALL 只提交 `config/project.template.json` 和 `config/user.project.template.json`，且模板内所有 key、secret、password 值 MUST 为空。Git MUST 忽略真实配置、`.env*`、IDE 文件、虚拟环境、依赖、构建产物、覆盖率、缓存、后端 var、SQLite 和日志文件。

#### Scenario: 检查敏感文件追踪边界
- **WHEN** 开发者运行仓库策略测试和 `git check-ignore`
- **THEN** 真实配置及敏感产物均被忽略，模板保持可提交且不包含非空凭据

### Requirement: 基础设施只声明允许的运行边界
基础说明 SHALL 规定未来 Compose 只托管 etcd、MinIO、Milvus、Attu 和 Alertmanager；后端、前端及官方 CLS MCP Server MUST 在主机运行。本变更 MUST NOT 创建应用 Dockerfile、`project.compose.json` 或应用 Compose 服务。

#### Scenario: 审查基础设施目录
- **WHEN** 开发者检查 foundation 的 `infra` 内容
- **THEN** 只能看到边界说明，不存在应用容器定义或产品服务实现

### Requirement: 基础质量门禁可重复执行
仓库 SHALL 提供 OpenSpec 验证、后端 Ruff/Pyright/pytest、contracts typecheck/test、前端 typecheck/test/build、secret 扫描和 `git diff --check` 门禁，并用真实锁文件保证依赖安装可重复。

#### Scenario: 执行完整 foundation 验收
- **WHEN** 开发者按照项目指南运行全部门禁
- **THEN** 所有命令成功退出，且 README 只说明已实现的骨架和验证方式
