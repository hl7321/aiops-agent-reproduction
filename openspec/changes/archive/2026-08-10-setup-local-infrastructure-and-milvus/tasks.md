## 1. Compose 与配置事实来源

- [x] 1.1 先为五服务白名单、固定镜像、依赖图、healthcheck、持久卷和 Alertmanager 只读配置编写失败策略测试
- [x] 1.2 先为 env_file/插值/应用容器/Dockerfile/日志上传/SOP seed 与 docker 镜像遗留字段编写失败黑名单测试
- [x] 1.3 创建 `infra/compose.yaml` 与最小 Alertmanager 配置，使 `docker compose config` 和策略测试通过
- [x] 1.4 更新两份配置模板及 ignored 本机配置，确认 Compose 是镜像版本唯一事实来源

## 2. VectorStore typed 配置与导入安全

- [x] 2.1 先为 JSON 深合并覆盖、缺失/非法字段、安全错误和环境变量隔离编写失败测试
- [x] 2.2 实现 frozen `VectorStoreSettings` 与显式 JSON loader，错误不得回显 token
- [x] 2.3 先为导入不读配置、不创建 PyMilvus client、不联网和无 public close 编写失败测试
- [x] 2.4 建立 `super_ai.vector_store` Protocol、错误和公开类型，保持模块 import 纯声明

## 3. Schema、索引和显式生命周期

- [x] 3.1 先为完整字段、1024 维、标量索引、HNSW/COSINE/M=16/efConstruction=200 编写失败测试
- [x] 3.2 实现官方 PyMilvus schema/index builder，禁用 dynamic field
- [x] 3.3 先为 lazy connect、未连接拒绝、幂等 initialize、load 和 fake factory 编写失败测试
- [x] 3.4 实现异步 `connect`/`initialize` 与同步 PyMilvus 线程卸载，不重复建 collection/index

## 4. Tenant-safe 数据操作

- [x] 4.1 先为 1024 维 chunk、可信 scalar/metadata、受保护 metadata 和批量本地预验证编写失败测试
- [x] 4.2 实现不可变 VectorChunk record 与 insert 映射
- [x] 4.3 先为 search ef=64、tenant/KB-only filter、escaping、空 KB 零连接和跨用户表达式编写失败测试
- [x] 4.4 实现 scoped search 与官方 response hit 映射，不接受 document/metadata Milvus filter
- [x] 4.5 先为完整 delete scope、空/越权 scope 拒绝和跨用户 delete filter 编写失败测试
- [x] 4.6 实现 delete-document，复用 P05 filter builder 且不加入 ownerUserId
- [x] 4.7 先为显式连接后的 health、服务版本和不初始化 collection 编写失败测试，再实现只读 health

## 5. 文档与治理

- [x] 5.1 更新 infra README、根/后端 README、AGENTS 和架构文档，明确主机应用、MinIO 用途与未实现产品能力
- [x] 5.2 增加本地基础设施运行与真实 Milvus smoke 指南，按实际服务可用性记录 smoke 状态
- [x] 5.3 运行后端定向测试与策略测试，确认本机 JSON 仍 ignored 且未 stage

## 6. 验证与归档准备

- [x] 6.1 运行 backend Ruff、strict Pyright、pytest 全门禁并修复问题
- [x] 6.2 运行 `docker compose -f infra/compose.yaml config`、相关 workspace 回归、`openspec validate --all` 与 `git diff --check`
- [x] 6.3 执行 `$openspec-verify-change`，修复全部 CRITICAL/WARNING 并确认 delta specs 可同步归档
