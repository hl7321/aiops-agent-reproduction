## MODIFIED Requirements

### Requirement: 基础设施只运行允许的本地依赖
仓库 SHALL 在 `infra/compose.yaml` 提供最终本地基础设施，Compose 服务集合 MUST 精确等于 etcd、MinIO、Milvus、Attu 和 Alertmanager。后端、前端及官方 CLS MCP Server MUST 在主机运行；Compose MUST NOT 创建应用镜像、应用 Dockerfile、`project.compose.json`、日志上传或 SOP seed。MinIO MUST 只作为 Milvus 依赖，不得被声明为应用文档对象存储。

#### Scenario: 审查基础设施目录
- **WHEN** 开发者检查 infra 内容并解析 Compose
- **THEN** 只看到五个允许的基础服务、运行配置和说明，不存在应用容器或产品数据 seed

#### Scenario: 主机运行应用
- **WHEN** 开发者按照项目指南启动本地环境
- **THEN** 只用 Compose 启动基础服务，并在主机分别运行 FastAPI、Vue 与官方 CLS MCP Server

## RENAMED Requirements

- FROM: `### Requirement: 基础设施只声明允许的运行边界`
- TO: `### Requirement: 基础设施只运行允许的本地依赖`
