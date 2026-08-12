## Context

P01 的 `infra/README.md` 只声明未来边界；P05 已实现 `VectorScope`、可信 metadata、JSON escaping、tenant/KB search filter 与完整 delete filter，但没有真实 Milvus client；P06 已建立只读显式 JSON 路径、typed validation、延迟外部 client 与脱敏模式。后端依赖已锁定 `pymilvus>=3,<4`。参见 proposal.md 与两份 delta specs。

Milvus v3.0-beta 官方 standalone Compose 仍由 etcd 与 MinIO 支撑；本项目按明确终态版本覆盖官方示例中的 etcd tag，并去除 `${DOCKER_VOLUME_DIRECTORY}` 等变量插值。PyMilvus 3 的 `MilvusClient` 构造即建立连接，collection schema/index builder 本身不联网，因此 client factory 必须只在显式 `connect()` 内调用。

## Goals / Non-Goals

**Goals：**

- 让 `infra/compose.yaml` 成为五个镜像版本和依赖图的唯一事实来源，并能由 Docker Compose V2 静态解析。
- 提供只消费本地 JSON 合并结果、可注入 fake、默认不阻塞 async 应用事件循环的 Milvus adapter。
- 复用 P05 scope helper，把搜索和删除 tenant 边界锁在 adapter 入口，而不是依赖未来 service 自觉检查。
- 以可审计 schema/index builder 固定 1024/HNSW/COSINE 参数，并让 initialize 可重复执行。

**Non-Goals：**

- 不实现知识库、文档、chunking、embedding pipeline、retrieval tool、RAG/Agent、日志上传、SOP seed 或产品 HTTP endpoint。
- 不把 MinIO 暴露为应用对象存储，不创建 bucket 初始化 job。
- 不在导入、FastAPI 启动或自动化测试中拉镜像/启动 Compose/连接真实 Milvus。
- 不虚构 `MilvusClient.close()`；进程级 client 释放策略等待官方稳定 public API 或后续运行时提案。

## Decisions

### 1. 单一固定 Compose，不再保留应用镜像配置

`infra/compose.yaml` 使用命名卷，固定：`quay.io/coreos/etcd:v3.5.18`、`minio/minio:RELEASE.2024-12-18T13-15-44Z`、`milvusdb/milvus:v3.0-beta`、`zilliz/attu:v2.5.12`、`prom/alertmanager:v0.28.1`。服务名固定为 `alertmanager/etcd/minio/milvus/attu`。Milvus 使用 `ETCD_ENDPOINTS=etcd:2379`、`MINIO_ADDRESS=minio:9000` 与 Woodpecker；Attu 使用容器内 `milvus:19530`；Alertmanager 只读挂载 `infra/alertmanager/alertmanager.yml`。

五个服务都声明 healthcheck 和命名持久卷。`depends_on.condition=service_healthy` 表达 Milvus→etcd/MinIO、Attu→Milvus。Compose 文件不使用顶层 `version`、profiles、env_file 或变量插值，使 `docker compose config` 输出确定。

替代方案是复刻官方 release Compose 或加入 backend/frontend；官方文件含 `${...}` 与不同 etcd tag，应用服务又违反主机运行边界，因此拒绝。镜像 tag 同时放 JSON 会产生双事实来源，因此删除/禁止 `docker.*Image*` 遗留。

### 2. typed vectorStore settings 与 client 生命周期分离

`super_ai.vector_store.config` 从 `load_project_config(project_path, user_path)` 的结果中只提取 `vectorStore`，使用 frozen、`extra="forbid"` Pydantic v2 model 校验 `uri`、`token`、`collectionName`。URI 只接受不含内嵌凭据的 HTTP(S)，collection name 使用 Milvus 标识符规则。错误只暴露字段路径，不回显 token。测试设置环境变量证明 loader 不读取它们。

`MilvusVectorStore` 构造只保存 settings/factory；`connect()` 首次在线程中调用 factory 并缓存 client，重复调用返回同一连接。`initialize()` 显式调用 connect 后检查 collection：不存在时一次性提交 schema/index，随后 load；存在时只确认/加载，不重建。`health()`、insert/search/delete 需要已连接 client（但空 KB search 在此检查之前返回）。

替代方案是在模块 import 或构造函数内建 client；这会破坏 import-safety 和测试隔离。每次操作临时 client 会放大连接成本且没有稳定 close API，因此拒绝。

### 3. 异步 adapter 包装官方同步 MilvusClient

adapter public 方法为 async；所有可能联网的同步 PyMilvus 调用通过 `asyncio.to_thread()` 执行。内部 `MilvusClientProtocol` 只声明已消费的方法，factory 可注入同步 fake。schema/index builder 使用官方无 I/O class helpers；不包装或声明不存在的 close。

替代方案是直接在事件循环调用同步 client，可能阻塞 FastAPI；切换仍在演进的 AsyncMilvusClient 会扩大 P07 兼容风险，因此本阶段采用稳定同步 API 加线程卸载。

### 4. schema 明确字段，不启用 dynamic field

schema 使用 `auto_id=False`、`enable_dynamic_field=False`：`chunkId` VARCHAR 主键；documentId、knowledgeBaseId、ownerUserId、tenantId 为 VARCHAR；content/source/createdAt 为 VARCHAR；metadata 为 JSON；vector 为 1024 维 FLOAT_VECTOR。长度上限在常量中集中定义。createdAt 使用 UTC ISO-8601 字符串，metadata 使用 JSON 对象。

index params 同时包含 vector HNSW/COSINE/M=16/efConstruction=200，以及 tenantId、knowledgeBaseId、documentId 的 INVERTED 标量索引。search 明确 `anns_field="vector"`、COSINE 与 `params.ef=64`。

替代方案是 dynamic `$meta` 或把所有业务字段塞入 JSON；这会削弱 schema 审计和标量过滤，违反 foundation 的规范化边界，因此拒绝。

### 5. record 和 scope 在 client 之前验证

`VectorChunk` 是不可变 record，保存 chunk/document/knowledge-base、正文、来源、UTC created_at、metadata 和 1024 维 vector。adapter insert 调用 P05 `build_vector_metadata()`，从 `VectorScope` 生成 tenantId/ownerUserId，并把相同归属写入独立标量；所有 records 完成校验后才进行一次 client.insert，避免部分本地验证失败。

search 接受 `VectorScope`、单个 1024 维 query vector 与 limit。先调用 `build_search_filter()`；返回 None 时立即 `[]`，完全不读取 client。表达式只含 tenantId 和 knowledgeBaseId；document/metadata 后过滤仍由 P05 `post_filter_hits` 留给未来 retrieval tool。返回 `VectorSearchHit` 只映射官方 response 的 chunk id、distance 与 entity。

delete-document 只接受 scope、knowledgeBaseId、documentId，并复用 `build_delete_filter()`；ownerUserId 只用于 metadata/标量追溯，不加入 search/delete expression。所有字符串 escaping 由 P05 的 JSON quoting 单点负责。

### 6. health 与 smoke 分开

health 在已 connect client 上调用 `get_server_version()`，返回不可变 `MilvusHealth(healthy=True, server_version=...)`；不调用 initialize，异常向上传递为安全 adapter error。自动化只用 fake。

`docs/runbooks/local-infrastructure.md` 记录 Compose config/up/ps/down 与可选真实 smoke。自动化先探测 19530；不可用时写明“未执行”，可用时才显式 connect/initialize/health 并报告实际结果。本次 change 不为通过门禁而自动拉镜像或启动服务。

## Risks / Trade-offs

- **Milvus v3.0-beta 和 PyMilvus 3 API 仍可能变化** → 用窄 Protocol 隔离，版本和 schema 参数由测试锁定，真实 smoke 单独记录。
- **Attu v2.5.12 对 Milvus 3 beta 的 UI 兼容可能有限** → 版本是项目终态输入，healthcheck 只验证 Attu 进程；不把 UI 功能声称为 adapter 验证。
- **同步 client 线程卸载有调度开销** → P07 优先兼容稳定 API；后续性能提案可在合同不变时替换 AsyncMilvusClient。
- **initialize 对已存在但 schema 漂移的 collection 不自动迁移** → 本阶段只保证新建与重复执行幂等；检测/迁移已有生产 collection 属于后续 schema migration change。
- **固定本地 MinIO 凭据只适用于 Milvus 依赖** → 不向应用配置或浏览器暴露，也不用于用户文档存储。

## Migration Plan

1. 增加 Compose/模板策略 RED 测试，再创建五服务 Compose、Alertmanager 配置和说明。
2. 增加 vectorStore typed settings 与 import-safety RED 测试，再实现配置和延迟 client Protocol。
3. 以 fake client 逐步锁定 schema/index、幂等 initialize、insert、search/delete scope 与 health。
4. 运行 `docker compose -f infra/compose.yaml config`、后端全门禁和 OpenSpec 验证；仅在 19530 已可用时执行真实 smoke。
5. verify 无 CRITICAL/WARNING 后同步主规格并归档。回滚删除 P07 adapter/Compose 文件并恢复 foundation 主规格；SQLite 与认证数据不受影响。
