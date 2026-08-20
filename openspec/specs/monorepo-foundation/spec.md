# Monorepo Foundation 规格

## Purpose

本能力为后续智能 OnCall Agent 功能提供可安装、可运行、可验证且默认保护服务端秘密的统一 monorepo 工程基础。

## Requirements

### Requirement: 仓库提供最终工程边界
仓库 SHALL 提供 `apps/backend`、`apps/frontend`、`packages/api-contracts`、`config`、`infra`、`scripts`、`openspec` 和 `docs` 目录，并通过根 workspace 命令统一调用 contracts、frontend 和 docs 的质量任务。

#### Scenario: 开发者检出基础仓库
- **WHEN** 开发者检出并安装本变更后的仓库
- **THEN** 所有最终目录均存在，且根命令能够定位相应 workspace 的脚本

### Requirement: 后端提供最小且导入安全的应用
后端 SHALL 提供可显式创建的应用和 `/health` 健康检查；`/health` MUST 通过共享 OpenAPI path 合同登记，并返回包含 foundation 状态与 request ID 的统一成功 envelope。导入后端模块期间 MUST NOT 连接 SQLite、Milvus、LLM 或 MCP。项目内 Python 导入 MUST 使用 `super_ai` 包路径，不得使用 `src.super_ai`。

#### Scenario: 调用健康检查
- **WHEN** 测试通过 app factory 创建后端应用并请求 `/health`
- **THEN** 响应成功，返回 `{ok:true,data:{status:"ok"},meta:{requestId}}`，且 `X-Request-ID` header 与 meta 一致

#### Scenario: 仅导入后端包
- **WHEN** Python 进程导入 `super_ai` 及其应用模块
- **THEN** 导入完成且没有建立任何外部服务或数据库连接

### Requirement: 项目配置使用本地 JSON 递归深合并
应用 SHALL 先读取显式传入的 `config/project.json`，再用 `config/user.project.json` 对对象字段进行递归深合并；数组和标量由用户配置覆盖。项目配置 MUST NOT 从 OS 环境变量读取。文件不存在、文件不是有效 JSON 或顶层不是 JSON object 时，加载器 MUST 返回包含配置路径和安全原因、但不包含文件内容或凭据的明确错误。

#### Scenario: 用户只覆盖嵌套标题
- **WHEN** 项目配置同时包含标题和 API 地址，而用户配置只覆盖标题
- **THEN** 合并结果使用用户标题并保留项目配置的 API 地址

#### Scenario: 测试注入临时配置
- **WHEN** 测试向配置加载器传入临时 JSON 路径
- **THEN** 加载器只读取这些显式路径且不依赖开发者本机真实值

#### Scenario: 配置文件不存在
- **WHEN** 显式项目或用户配置路径不存在
- **THEN** 加载器返回指出该路径不存在的安全配置错误

#### Scenario: 配置不是 JSON object
- **WHEN** 配置文件包含非法 JSON 或合法 JSON 数组、字符串等非对象顶层
- **THEN** 加载器区分无效 JSON 与非对象顶层，且错误不回显配置内容

### Requirement: 浏览器配置遵守公开 allowlist
前端构建 SHALL 只向浏览器注入 `frontend.title`、`frontend.apiBaseUrl` 和明确标记为 public 的 analytics key。LLM、model capability、vector store、CLS、MCP、Prometheus、日志上传、AIOps demo、MinIO 的 key、secret、token、email 或 password MUST NOT 进入浏览器 bundle。

#### Scenario: 构建配置包含 sentinel secret
- **WHEN** 临时服务端配置的任一非公开 section 包含唯一 sentinel secret 并执行前端生产构建
- **THEN** 构建成功，且递归扫描 `dist` 不得找到该 sentinel

#### Scenario: 浏览器读取公开配置
- **WHEN** 前端启动并读取构建注入配置
- **THEN** 只能获得 allowlist 中的 typed 字段，不能访问完整项目 JSON

### Requirement: 敏感本机文件默认不受 Git 追踪
仓库 SHALL 只提交 `config/project.template.json` 和 `config/user.project.template.json`。模板 MUST 包含最终应用所需的 `app`、`backend`、`frontend`、`llm`、`modelCapabilities`、`vectorStore`、`mcp`、`clsMcpServer`、`prometheusAlerts`、`clsLogUpload` 与 `aiopsDemo` section，其中 `aiopsDemo` 至少包含 `backendBaseUrl`、`email`、`displayName`、`password`、`pollIntervalSeconds` 与 `indexWaitSeconds`；所有 key、secret、token 和 password 模板值 MUST 为空。本机配置 SHALL 从模板创建、由开发者只在被忽略的用户配置中填写凭据，且 MUST 保持 Git ignored。Git 还 MUST 忽略 `.env*`、IDE 文件、虚拟环境、依赖、构建产物、覆盖率、缓存、后端 var、SQLite 和日志文件。

#### Scenario: 检查敏感文件追踪边界
- **WHEN** 开发者运行仓库策略测试和 `git check-ignore`
- **THEN** 真实配置及敏感产物均被忽略，模板包含最终 section 且不包含非空凭据

#### Scenario: 从模板创建本机配置
- **WHEN** 当前 workspace 为构建创建 project 与 user project 本机文件
- **THEN** 文件可被 JSON loader 使用、保持 Git ignored，且不会被 stage

### Requirement: 基础设施只运行允许的本地依赖
仓库 SHALL 在 `infra/compose.yaml` 提供最终本地基础设施，Compose 服务集合 MUST 精确等于 etcd、MinIO、Milvus、Attu 和 Alertmanager。后端、前端及官方 CLS MCP Server MUST 在主机运行；Compose MUST NOT 创建应用镜像、应用 Dockerfile、`project.compose.json`、日志上传或 SOP seed。MinIO MUST 只作为 Milvus 依赖，不得被声明为应用文档对象存储。

#### Scenario: 审查基础设施目录
- **WHEN** 开发者检查 infra 内容并解析 Compose
- **THEN** 只看到五个允许的基础服务、运行配置和说明，不存在应用容器或产品数据 seed

#### Scenario: 主机运行应用
- **WHEN** 开发者按照项目指南启动本地环境
- **THEN** 只用 Compose 启动基础服务，并在主机分别运行 FastAPI、Vue 与官方 CLS MCP Server

### Requirement: 基础质量门禁可重复执行
仓库 SHALL 提供 OpenSpec 验证、后端 Ruff/Pyright/pytest、contracts typecheck/test、前端 typecheck/test/build、secret 扫描和 `git diff --check` 门禁，并用真实锁文件保证依赖安装可重复。

#### Scenario: 执行完整 foundation 验收
- **WHEN** 开发者按照项目指南运行全部门禁
- **THEN** 所有命令成功退出，且 README 只说明已实现的骨架和验证方式

### Requirement: MCP 回退配置与凭据遵守本地安全边界
后端 SHALL 只从 `project.json` 与 `user.project.json` 的深合并结果读取 `clsMcpServer`，不得从 OS 环境变量获取 MCP 项目配置。模板中 baseUrl、secretId、secretKey 等凭据字段 MUST 为空，且前端构建 allowlist MUST NOT 暴露任何 MCP/CLS 字段。`clsMcpServer.baseUrl` 只表示主机上真实服务的回退地址，不得解释为已连通 profile。文档 MUST 明确官方 CLS MCP Server 在主机运行、不属于 Compose，并禁止把 token/secret 放入 MCP URL query；P18 MUST NOT 声称已完成 P26 的启动与凭据指南。

#### Scenario: 前端构建扫描 MCP sentinel
- **WHEN** 临时本地 JSON 的 mcp 或 clsMcpServer section 含唯一 sentinel 并执行前端生产构建
- **THEN** 构建成功且 dist 不包含 sentinel、baseUrl、secretId 或 secretKey 值

#### Scenario: 空 CLS baseUrl
- **WHEN** 深合并配置的 clsMcpServer.baseUrl 为空
- **THEN** 后端不创建回退 MCP client，不读取环境变量且不生成假连接
