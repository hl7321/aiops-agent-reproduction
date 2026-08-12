## Why

P01 只声明了基础设施边界，P05 只提供不连接 Milvus 的 tenant filter 合同；后续知识索引需要一个版本固定、可本地启动且不会把应用塞回 Compose 的最终运行边界，以及真正执行 owner-scoped 操作的 Milvus adapter。P07 在产品知识库功能之前补齐这两个基础能力，避免镜像版本、连接生命周期和 tenant filter 在后续提案中各自漂移。

## What Changes

- 新增 `infra/compose.yaml`，只运行 alertmanager、etcd、minio、milvus、attu 五个服务，并固定 etcd v3.5.18、MinIO RELEASE.2024-12-18T13-15-44Z、Milvus v3.0-beta、Attu v2.5.12、Alertmanager v0.28.1。
- 为五个服务建立持久卷和 healthcheck；Milvus standalone 依赖 etcd/MinIO，Attu 依赖 Milvus，Alertmanager 只读挂载最小配置并暴露 9093。
- 明确禁止 backend、frontend、cls-mcp-server、`env_file`、`${...}`、应用镜像、应用 Dockerfile、日志上传和 SOP seed；MinIO 只作为 Milvus 内部依赖。
- 删除配置模板中若存在的 `docker.appImageTag`、`docker.clsMcpServerVersion`、`docker.milvusImage` 遗留段，使 Compose 成为镜像版本唯一事实来源。
- 新增 `super_ai.vector_store` typed 本地 JSON 配置、可注入 PyMilvus client Protocol 和延迟连接的 Milvus adapter；导入模块不读取本机配置、不创建 client、不联网。
- 新增显式 `connect`/`initialize`、health、insert、search、delete-document 生命周期；本阶段不声明虚构的 public close API。
- 固定 1024 维 collection schema、HNSW/COSINE（M=16、efConstruction=200、search ef=64）和 tenant-safe search/delete 表达式。
- 使用自动化 fake client 验证 schema、索引、幂等 initialize、跨用户隔离、escaping、空 scope 拒绝与 import-safety；真实 Milvus smoke 只在服务可用时人工执行并如实记录。
- 本变更不实现知识库 CRUD、文档解析/上传、embedding 生产流水线、retrieval tool、Agent/RAG、日志上传或 SOP seed。

## Capabilities

### New Capabilities

- `local-infrastructure-and-milvus`: 定义最终五服务本地 Compose 边界，以及显式、可注入、tenant-safe 的 Milvus collection 与数据操作合同。

### Modified Capabilities

- `monorepo-foundation`: 把“只声明未来基础设施边界”更新为实际存在但仍只包含五个基础服务的最终 Compose 边界，并移除重复镜像版本配置。

## Impact

- 新增 `infra/compose.yaml`、Alertmanager 配置、基础设施策略测试和运行说明。
- 新增 `apps/backend/src/super_ai/vector_store` 与 fake-based 后端测试；复用既有 `pymilvus>=3,<4`、P01 JSON loader 和 P05 `VectorScope`/filter builder，不增加产品 endpoint 或数据库迁移。
- 更新配置模板、AGENTS、README 与架构/运行手册；本机 `project.json` 保持 ignored，Compose 中不消费应用秘密。
