## Why

后续认证、Chat、知识、任务、MCP、AIOps、反馈和审计都需要一致的持久化边界；若各领域直接依赖 SQLite 或 ORM model，将难以测试、替换数据库并容易在模块导入时产生外部副作用。因此本阶段先建立统一、可迁移、可注入的 SQLite repository foundation，而不提前实现任何领域 CRUD。

## What Changes

- 使用 SQLAlchemy 2 async 与 aiosqlite 建立声明式 `Base`、显式 async engine/session factory 和统一事务约定。
- 从本地 `project.json` 与 `user.project.json` 深合并结果读取数据库 URL，不把 OS 环境变量作为项目配置来源。
- 以 Alembic 作为 schema 迁移唯一权威，提供 async 迁移环境、首个基础迁移和测试 migration helper。
- 定义与 ORM 解耦的 Repository Protocol、不可变 record，以及统一 ID、UTC 时间和 JSON 序列化工具。
- 将 SQLite 实现限定在 `super_ai.memory.sqlite` 与 `super_ai.memory.extended_sqlite`，保留未来 PostgreSQL 替换边界。
- 提供只使用临时 SQLite 数据库的测试基础，覆盖迁移、metadata 一致性、并发 session、回滚、repository contract、配置注入和 import-safety。
- 明确本变更不实现认证、Chat、知识、任务、MCP、AIOps、反馈或审计的领域表与 CRUD。

## Capabilities

### New Capabilities

- `sqlite-repository-foundation`: 定义可替换、可测试、导入安全的 async SQLite 持久化、迁移和 Repository 基础合同。

### Modified Capabilities

无。

## Impact

- 后端新增 `super_ai.memory` 核心边界、SQLite adapter、迁移配置和测试工具。
- `config/project.template.json` 增加无凭据的数据库配置示例；本机真实配置仍被 Git 忽略。
- 后端测试与项目指南增加迁移和 persistence 验证命令。
- 不新增 HTTP endpoint，不改变 P02 的 HTTP/SSE 合同，不连接任何外部数据库服务。
