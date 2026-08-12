# Durable Background Job Runtime Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 SQLite 持久化、owner-safe、可租约恢复的后台任务运行时及共享管理 API。

**Architecture:** 领域层定义冻结 record、Repository Protocol、handler registry 与 worker 状态机；SQLAlchemy ORM 和原子 claim 实现在 `super_ai.memory.extended_sqlite`。FastAPI lifespan 管理数据库和 worker pool，共享 contracts 先定义 DTO/path，再由 Pydantic 与路由实现对应形状。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2 async、aiosqlite、Alembic、pytest/pytest-asyncio、TypeScript 5.6。

---

### Task 1: 固化合同与数据库验收

- [x] 扩展 TypeScript/Pydantic 合同测试，覆盖任务 DTO、错误和四个受保护 path。
- [x] 增加 migration/metadata 测试，断言精确列集合、索引和禁止列。
- [x] 运行定向测试并确认因实现缺失而失败。

### Task 2: 实现领域与 SQLite Repository

- [x] 增加冻结 record、状态、Protocol 与服务错误。
- [x] 增加 ORM models、Alembic migration 和 owner-scoped CRUD/event 查询。
- [x] 实现原子 claim、heartbeat、完成、失败退避与过期回收。
- [x] 运行 Repository、迁移、并发和 owner 隔离测试。

### Task 3: 实现 handler registry 与 worker runtime

- [x] 用 fake handler 测试成功、失败重试、timeout、协作取消、restart 与断连重放。
- [x] 实现 registry、execution context、默认并发/lease/poll 和 managed worker lifecycle。
- [x] 测试 lifespan 启停和 import-safety。

### Task 4: 实现共享 API

- [x] 先增加 API 认证、owner 隔离、列表/详情/取消/重试和 envelope 测试。
- [x] 实现 Pydantic DTO、service/router 与 app 注册。
- [x] 验证 FastAPI OpenAPI 与机器可读 manifest 一致。

### Task 5: 完整验证与归档

- [x] 运行 migration、backend Ruff/Pyright/pytest、contracts typecheck/test、OpenSpec validate 与 git diff check。
- [x] 使用 openspec-verify-change 检查完整性、正确性和一致性，修复所有 CRITICAL 并处理 WARNING。
- [x] 同步 delta specs，归档 change，并再次验证仓库状态。
