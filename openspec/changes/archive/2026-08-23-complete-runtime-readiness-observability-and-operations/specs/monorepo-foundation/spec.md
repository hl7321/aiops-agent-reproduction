## ADDED Requirements

### Requirement: 最终交付文档与平台启动入口准确可复现
根 README SHALL 使用简体中文准确列出已实现能力、最终目录、本机模板复制、访问 URL、手动启动与全量验证命令。macOS、Linux 与 Windows 安装指南 SHALL 分别覆盖 Git、Docker、Node/npm、uv 和官方 CLS MCP；运维文档 SHALL 说明探针、轻量指标、安全日志和真实 fixture 副作用边界。README 与文档 MUST NOT 声称未执行的真实外部链路已通过。

#### Scenario: 新开发者按平台文档启动
- **WHEN** 新开发者在受支持平台阅读 README 和对应 setup 文档
- **THEN** 能区分五服务 Compose 与主机应用，找到模板、命令、URL、日志和验证入口

### Requirement: 仓库不保留废弃应用容器资产
仓库 MUST NOT 包含应用 `app.Dockerfile`、`project.compose.json`、`create_compose_app` 或其死引用。Compose MUST 继续只包含 etcd、MinIO、Milvus、Attu 与 Alertmanager。

#### Scenario: 扫描最终仓库
- **WHEN** 仓库治理测试扫描文件名、代码、脚本和文档引用
- **THEN** 不存在废弃应用容器资产或引用，Compose 服务白名单保持不变

### Requirement: 最终全平台自动门禁不可降级
交付 SHALL 运行 `openspec validate --all`、contracts typecheck/test、backend Alembic/Ruff/strict Pyright/pytest、frontend typecheck/test/build、`docker compose config`、`git diff --check` 与当前平台脚本语法门禁。实现 MUST NOT 通过删除测试、降低 strict 配置或使用 fake 外部结论绕过失败。

#### Scenario: 执行最终自动门禁
- **WHEN** 开发者在无真实 secret 的受支持开发环境执行文档列出的全量命令
- **THEN** 所有可执行命令成功退出，测试数量与 strict 配置没有为通过而降低
