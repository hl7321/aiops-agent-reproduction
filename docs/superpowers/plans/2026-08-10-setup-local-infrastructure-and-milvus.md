# Local Infrastructure and Milvus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立只含五个基础服务的最终 Compose，以及导入安全、显式连接、tenant-safe 的 PyMilvus 3 adapter。

**Architecture:** Compose 独立固定镜像与依赖图；后端从显式 JSON 深合并结果构造 frozen settings，通过 client Protocol/factory 延迟创建官方 MilvusClient。adapter public API 为 async，以 `asyncio.to_thread` 包装同步调用，并在接触 client 前复用 P05 scope helper 完成本地验证和空 KB 短路。

**Tech Stack:** Docker Compose V2、Milvus v3.0-beta、PyMilvus 3、Pydantic v2、Python >=3.10、pytest/pytest-asyncio、Ruff、strict Pyright。

## Global Constraints

- Compose 服务精确为 alertmanager、etcd、minio、milvus、attu，不包含任何应用服务或 seed。
- 镜像固定 etcd v3.5.18、MinIO RELEASE.2024-12-18T13-15-44Z、Milvus v3.0-beta、Attu v2.5.12、Alertmanager v0.28.1。
- 配置只从 project.json + user.project.json 深合并结果读取，不读取 OS 环境变量。
- collection 使用 1024 维、HNSW/COSINE、M=16、efConstruction=200、search ef=64。
- search filter 只含 tenantId + allowedKnowledgeBaseIds；delete filter 含 tenantId + knowledgeBaseId + documentId。
- import 不得创建 client/联网/初始化 collection；不声明 public close。

---

### Task 1: Compose policy and final topology

**Files:**
- Create: `tests/test_local_infrastructure_policy.py`
- Create: `infra/compose.yaml`
- Create: `infra/alertmanager/alertmanager.yml`
- Modify: `infra/README.md`
- Modify: `config/project.template.json`
- Modify: `config/user.project.template.json`

**Interfaces:**
- Consumes: Docker Compose V2 `config --format json`。
- Produces: 可静态验证的五服务 topology 和唯一镜像事实来源。

- [ ] **Step 1: 写失败测试**，用 subprocess 解析 Compose JSON，断言精确 service/image、depends_on、healthcheck、volumes、只读 mount，并扫描 `env_file`、`${`、应用/seed 黑名单。
- [ ] **Step 2: 运行 `cd apps/backend && uv run pytest ../../tests/test_local_infrastructure_policy.py -q`**，确认因 `infra/compose.yaml` 缺失失败。
- [ ] **Step 3: 创建最小 Compose/Alertmanager 配置**，使用命名卷和 `condition: service_healthy`，不使用变量插值。
- [ ] **Step 4: 运行策略测试和 `docker compose -f infra/compose.yaml config --format json`**，确认均成功。

### Task 2: Typed vector store settings and import boundary

**Files:**
- Create: `apps/backend/src/super_ai/vector_store/config.py`
- Create: `apps/backend/src/super_ai/vector_store/errors.py`
- Create: `apps/backend/src/super_ai/vector_store/types.py`
- Create: `apps/backend/src/super_ai/vector_store/__init__.py`
- Create: `apps/backend/tests/vector_store/test_config.py`
- Create: `apps/backend/tests/vector_store/test_import_safety.py`

**Interfaces:**
- Produces: `load_vector_store_settings(project_path: Path, user_path: Path) -> VectorStoreSettings`；`MilvusClientProtocol`；`VectorStoreError`。

- [ ] **Step 1: 写配置/导入失败测试**，覆盖 nested override、非法 URI/name、安全 token 错误、环境变量隔离以及 patch client/socket/config 后的子进程 import。
- [ ] **Step 2: 运行定向测试确认 RED**，缺少 `super_ai.vector_store`。
- [ ] **Step 3: 实现 frozen Pydantic settings 和 Protocol**，只从 `load_project_config` 提取 `vectorStore`，模块级不实例化任何 client。
- [ ] **Step 4: 运行定向测试确认 GREEN**。

### Task 3: Schema/index builders and lifecycle

**Files:**
- Create: `apps/backend/src/super_ai/vector_store/schema.py`
- Create: `apps/backend/src/super_ai/vector_store/adapter.py`
- Create: `apps/backend/tests/vector_store/fakes.py`
- Create: `apps/backend/tests/vector_store/test_schema.py`
- Create: `apps/backend/tests/vector_store/test_lifecycle.py`

**Interfaces:**
- Produces: `build_collection_schema()`；`build_index_params()`；`MilvusVectorStore.connect()`；`initialize()`。

- [ ] **Step 1: 写 schema/index RED 测试**，通过官方对象的 `to_dict()`/迭代参数断言十个字段、1024 维、INVERTED 与 HNSW 参数。
- [ ] **Step 2: 实现纯 builder**，使用 `MilvusClient.create_schema/prepare_index_params`，dynamic field=false。
- [ ] **Step 3: 写 lifecycle RED 测试**，fake 记录 factory/has/create/load 调用，两次 initialize 只创建一次。
- [ ] **Step 4: 实现 `connect/initialize`**，所有 client 调用通过 `asyncio.to_thread`，未连接 operation 抛出稳定错误。
- [ ] **Step 5: 运行 schema/lifecycle 测试确认 GREEN**。

### Task 4: Insert/search/delete/health

**Files:**
- Create: `apps/backend/src/super_ai/vector_store/records.py`
- Create: `apps/backend/tests/vector_store/test_insert.py`
- Create: `apps/backend/tests/vector_store/test_search.py`
- Create: `apps/backend/tests/vector_store/test_delete_and_health.py`
- Modify: `apps/backend/src/super_ai/vector_store/adapter.py`

**Interfaces:**
- Produces: frozen `VectorChunk`、`VectorSearchHit`、`MilvusHealth`；async `insert/search/delete_document/health`。

- [ ] **Step 1: 写 insert RED 测试**，合法 entity 同时含 scalar/metadata tenant-owner；维数/受保护字段错误时 fake 未调用。
- [ ] **Step 2: 实现 record validation 和批量 entity mapping**，先完全验证再一次 insert。
- [ ] **Step 3: 写 search RED 测试**，断言 COSINE/ef=64、tenant/KB-only expression、特殊字符 escaping、两用户隔离、空 KB factory=0。
- [ ] **Step 4: 实现 search**，先 scope filter，后 require client，映射官方 nested results。
- [ ] **Step 5: 写 delete/health RED 测试**，断言完整 filter、空/越权拒绝、两用户 filter、health 只调用 get_server_version。
- [ ] **Step 6: 实现 delete/health 并运行全部 vector_store 测试确认 GREEN**。

### Task 5: Documentation, gates, verify and archive

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `apps/backend/README.md`
- Modify: `infra/README.md`
- Create: `docs/architecture/vector-store.md`
- Create: `docs/runbooks/local-infrastructure.md`

**Interfaces:**
- Produces: 可复制的 config/up/down/smoke 命令与明确未实现边界。

- [ ] **Step 1: 更新文档**，声明主机运行应用、MinIO 仅为 Milvus、无 close、真实 smoke 状态。
- [ ] **Step 2: 运行 backend Ruff/Pyright/pytest、Compose config、workspace 回归、OpenSpec 和 diff 门禁**。
- [ ] **Step 3: 按 verify skill 逐条映射 Requirement/Scenario，修复全部 CRITICAL/WARNING**。
- [ ] **Step 4: 同步两份 delta specs，重新跑门禁后归档 change**。
