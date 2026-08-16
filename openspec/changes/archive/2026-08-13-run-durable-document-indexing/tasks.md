## 1. 合同与持久化

- [x] 1.1 先编写 DocumentIndexTask DTO、五种状态、三种 OpenAPI 操作和无 jobId 的共享合同失败测试
- [x] 1.2 先编写 document_index_tasks migration、metadata、状态约束、resource 关联和 owner scope Repository 失败测试
- [x] 1.3 实现 TypeScript/Pydantic contracts、机器可读 manifest、Alembic revision、ORM record 与 SQLite Repository

## 2. Durable 索引 handler

- [x] 2.1 先编写 owner-scoped 文档重读、统一 splitter、23 chunks 的 10/10/3 embedding 保序和向量形状失败测试
- [x] 2.2 先编写 Milvus initialize→scoped delete→单次 insert 顺序、完整 metadata 和稳定 chunkId 测试
- [x] 2.3 实现索引领域 service/handler、短事务状态推进、脱敏失败持久化和真实错误重抛
- [x] 2.4 先编写取消、worker lease 重启恢复、失败后 retry 来源和文档不误标成功测试
- [x] 2.5 把 document.index handler 注册到 P09 registry/lifespan，禁止临时 create_task 与 import-time client

## 3. API 与客户端显式调度

- [x] 3.1 先编写上传后零任务、显式首次创建、手动重建、详情、retry、owner 隔离和统一 envelope API 测试
- [x] 3.2 实现 POST documents/{document}/index-tasks、GET index-tasks/{task}、POST {task}:retry 路由和依赖注入
- [x] 3.3 为前端 typed knowledge transport 编写上传成功后显式创建任务的顺序测试并实现最小客户端方法，不实现知识 UI

## 4. 一致性与安全

- [x] 4.1 更新 KnowledgeDocument indexStatus 为 pending/running/succeeded/failed/cancelled，并验证 queued→pending 映射
- [x] 4.2 增加 Repository 参数治理、跨用户外部调用短路、import-safety 和无假向量/无 jobId 静态策略测试
- [x] 4.3 记录真实 Qwen+Milvus smoke 命令和执行条件；无有效 ignored JSON 或服务不可用时明确标记未执行

## 5. 验证与归档

- [x] 5.1 运行 `uv run alembic upgrade head`、Ruff、strict Pyright 和 backend 全量 pytest
- [x] 5.2 运行 contracts typecheck/test、受影响 frontend typecheck/test/build、`openspec validate --all` 和 `git diff --check`
- [x] 5.3 使用 openspec-verify-change 逐项核对任务、需求、场景和设计，修复全部 CRITICAL/WARNING
- [x] 5.4 同步三个 delta specs、归档 change，并复检无 active change 与格式门禁
