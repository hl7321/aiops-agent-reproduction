## MODIFIED Requirements

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
