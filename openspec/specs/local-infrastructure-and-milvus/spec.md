# Local Infrastructure and Milvus 规格

## Purpose

本能力提供与项目终态一致的五服务本地基础设施，以及显式连接、可注入、导入安全并强制 tenant/knowledge-base scope 的 Milvus 向量存储基础，为后续知识索引和检索功能提供不可绕过的运行边界。

## Requirements

### Requirement: Compose 是五个基础服务镜像版本的唯一事实来源
仓库 SHALL 提供 `infra/compose.yaml`，且服务集合 MUST 精确等于 `alertmanager`、`etcd`、`minio`、`milvus`、`attu`。Compose MUST 固定 etcd `v3.5.18`、MinIO `RELEASE.2024-12-18T13-15-44Z`、Milvus `v3.0-beta`、Attu `v2.5.12` 与 Alertmanager `v0.28.1`；项目 JSON 模板 MUST NOT 再声明 `docker.appImageTag`、`docker.clsMcpServerVersion` 或 `docker.milvusImage` 等重复镜像版本。

#### Scenario: 校验服务和镜像白名单
- **WHEN** 自动化测试解析最终 Compose 配置
- **THEN** 只发现五个允许服务，且每个镜像严格使用指定版本

#### Scenario: 检查配置模板的镜像来源
- **WHEN** 自动化测试扫描项目与用户配置模板
- **THEN** 模板不存在 docker 镜像版本遗留字段，镜像版本只在 Compose 中出现

### Requirement: 五个服务具有确定依赖、持久化和健康检查
etcd、MinIO、Milvus、Attu 与 Alertmanager MUST 各自声明持久卷和 healthcheck。Milvus standalone MUST 使用 etcd 与 MinIO 并依赖二者健康；Attu MUST 依赖 Milvus 健康；Alertmanager MUST 以只读方式挂载仓库配置、持久化运行数据并向主机暴露 9093。

#### Scenario: 解析 Compose 运行图
- **WHEN** 开发者执行 `docker compose -f infra/compose.yaml config`
- **THEN** 配置成功，Milvus/Attu 依赖图、五个 healthcheck、持久卷及 Alertmanager 只读配置均被保留

#### Scenario: 说明 MinIO 的用途
- **WHEN** 开发者阅读基础设施运行说明
- **THEN** 文档只把 MinIO 描述为 Milvus 依赖，不把它声明为应用文档对象存储

### Requirement: 应用和数据 seed 保持在 Compose 之外
Compose MUST NOT 包含 backend、frontend、cls-mcp-server、应用镜像、应用 Dockerfile、日志上传或 SOP seed，MUST NOT 使用 `env_file` 或 `${...}` 变量插值。FastAPI、Vue 和官方 CLS MCP Server SHALL 在主机运行，且仓库 MUST NOT 新增应用 Dockerfile 或 `project.compose.json`。

#### Scenario: 扫描废弃全栈 Compose 资产
- **WHEN** 自动化策略测试扫描 Compose、infra、配置模板和仓库文件名
- **THEN** 不存在被禁止的服务、字段、插值、应用容器或 seed 资产

### Requirement: 向量存储配置只来自显式本地 JSON 合并结果
Milvus adapter SHALL 只消费显式传入的 `project.json` 与 `user.project.json` 深合并结果中的 typed `vectorStore` section，至少包含非空 HTTP(S) `uri`、`token` 和合法 `collectionName`。配置 MUST NOT 从 OS 环境变量读取；缺失或非法字段 MUST 在创建 client 前返回安全、可定位的配置错误。

#### Scenario: 用户配置覆盖向量存储字段
- **WHEN** 用户配置只覆盖 vectorStore token 或 collectionName
- **THEN** typed settings 使用覆盖值并保留项目配置中的其他字段

#### Scenario: 环境变量不能补充缺失配置
- **WHEN** 进程环境存在 Milvus URI/token 但显式 JSON 缺少有效 vectorStore 字段
- **THEN** validation 在创建 client 前失败且不采用环境变量

### Requirement: Milvus client 具有延迟且幂等的显式生命周期
导入 `super_ai.vector_store` MUST NOT 创建 client、读取本机配置、连接网络或初始化 collection。adapter SHALL 提供显式 `connect`、`initialize`、`health`、`insert`、`search` 与 `delete_document`，并允许注入受控 fake client；当前 adapter MUST NOT 声明 PyMilvus 不存在的 public close 生命周期。重复 initialize MUST 保持幂等，不重复创建 collection 或索引。

#### Scenario: 仅导入向量模块
- **WHEN** 独立进程在 client 创建和网络连接被禁止时导入全部向量模块
- **THEN** 导入成功且没有配置读取、client 实例或外部 I/O

#### Scenario: 显式连接并重复初始化
- **WHEN** 调用方先 connect，再连续两次 initialize
- **THEN** client 只由显式路径创建一次，collection/index 只在不存在时建立，两次调用均可成功

#### Scenario: 注入 fake client
- **WHEN** 测试提供 fake client factory
- **THEN** 所有生命周期通过同一 adapter 合同执行且不连接真实 Milvus

### Requirement: Collection schema 与索引参数固定可审计
collection MUST 使用 1024 维 float vector，并至少包含 `chunkId` 主键、`documentId`、`knowledgeBaseId`、`ownerUserId`、`tenantId`、`content`、`source`、`createdAt`、`metadata` 与 `vector` 字段。向量索引 MUST 使用 HNSW/COSINE、M=16、efConstruction=200，搜索 MUST 使用 ef=64；`tenantId`、`knowledgeBaseId` 与 `documentId` 等可过滤标量 MUST 建立标量索引。

#### Scenario: 初始化新 collection
- **WHEN** adapter 对不存在的 collection 执行 initialize
- **THEN** 创建的 schema 包含完整字段和 1024 维 vector，索引参数精确匹配 HNSW/COSINE 与三个指定参数，并加载 collection

### Requirement: 插入同时保存可信 tenant 与 owner 追溯信息
插入 chunk 时 adapter MUST 将 scope 中的 `tenantId` 与 `ownerUserId` 同时写入独立标量，并在 metadata 中保留相同追溯字段、knowledgeBaseId 与 documentId；调用方 metadata MUST NOT 覆盖这些受保护字段。vector 维数不是 1024、scope 不完整或 knowledge base 不在允许集合时 MUST 在调用 Milvus insert 前拒绝。

#### Scenario: 插入受保护 chunk
- **WHEN** 当前用户向允许的知识库插入合法 1024 维 chunk
- **THEN** Milvus entity 包含全部 collection 字段，标量和 metadata 中的 tenant/owner 归属一致

#### Scenario: 拒绝非法插入
- **WHEN** vector 维数错误或额外 metadata 尝试覆盖 tenant/owner/document/knowledge-base 字段
- **THEN** adapter 在调用 Milvus 前拒绝且不写入部分 entity

### Requirement: 搜索只使用 tenant 与允许知识库粗召回 scope
搜索表达式 MUST 只由结构化 scope 生成 `tenantId + allowedKnowledgeBaseIds`，MUST NOT 重复加入 `ownerUserId`。allowed KB 为空时 MUST 直接返回空列表且不得创建或访问 client；非空搜索 MUST 使用 COSINE、ef=64。document 或 metadata 条件 MUST 留给 retrieval tool 对 owner-scoped 粗召回结果做后过滤，不得进入 Milvus search expression。

#### Scenario: 两个用户执行搜索
- **WHEN** 用户 A 与用户 B 使用相同向量和知识库标识分别搜索
- **THEN** 两次 Milvus filter 分别包含各自 tenantId，均不包含 ownerUserId、document 或 metadata 条件

#### Scenario: 搜索 scope 正确转义
- **WHEN** tenant 或知识库 ID 包含引号、反斜杠等特殊字符
- **THEN** filter 使用安全字符串转义且不能改变表达式结构

#### Scenario: 空知识库搜索短路
- **WHEN** allowedKnowledgeBaseIds 为空且 adapter 尚未连接
- **THEN** 返回空列表，client factory 和 search 均未调用

### Requirement: 删除、健康检查和真实 smoke 不扩大边界
文档向量删除表达式 MUST 同时包含非空 `tenantId + knowledgeBaseId + documentId`，MUST NOT 加入 ownerUserId 或退化为宽范围删除；knowledge base 必须属于当前允许 scope。health SHALL 只在显式连接后调用官方 client 的只读服务检查并返回健康状态/版本，不初始化 collection。真实 Milvus smoke SHALL 只在五服务可用且开发者显式执行时运行；未执行或服务不可用时 MUST 如实记录，不能声称通过。

#### Scenario: 两个用户删除同名文档
- **WHEN** 用户 A 与用户 B 对相同 knowledgeBaseId/documentId 分别执行删除
- **THEN** 两次 delete filter 分别包含各自 tenantId，不能删除另一个用户的数据

#### Scenario: 拒绝不完整删除 scope
- **WHEN** tenant、knowledge base、document 任一为空或知识库不在允许 scope
- **THEN** adapter 在调用 client.delete 前拒绝操作

#### Scenario: 显式健康检查
- **WHEN** adapter 已 connect 且 health 调用成功
- **THEN** 返回 healthy 与服务版本，且没有创建或修改 collection

#### Scenario: 未运行真实 Milvus smoke
- **WHEN** 自动化门禁只使用 fake client 或本机五服务不可用
- **THEN** 运行文档明确记录真实 smoke 未执行，不把 fake 测试描述为真实服务连通性通过
