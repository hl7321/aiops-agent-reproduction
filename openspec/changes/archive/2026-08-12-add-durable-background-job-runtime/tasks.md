## 1. 合同与数据模型

- [x] 1.1 先编写 BackgroundJob DTO、错误目录和四个受保护 OpenAPI path 的 TypeScript/Pydantic 合同测试
- [x] 1.2 先编写 background_jobs/background_job_events migration、metadata、一致性和禁止虚构列测试
- [x] 1.3 实现共享 contracts、领域冻结 record、状态枚举和 Repository Protocol
- [x] 1.4 实现 SQLAlchemy models 与 Alembic migration，并验证 fresh database upgrade

## 2. Owner-scoped Repository

- [x] 2.1 先编写 list/get/cancel/retry/list_events 的 owner 隔离与不可枚举错误测试
- [x] 2.2 实现 owner-scoped enqueue、查询、取消、重试与单调事件序列
- [x] 2.3 先编写并发唯一领取、heartbeat、过期 lease 和最大尝试次数测试
- [x] 2.4 实现原子 claim、续租、成功/失败/取消状态转换与过期回收

## 3. Worker runtime

- [x] 3.1 先用 fake handler 编写 registry、restart、retry/backoff、timeout 与协作取消测试
- [x] 3.2 实现按 kind 注册的 handler registry、执行上下文和脱敏边界
- [x] 3.3 实现默认 concurrency=2、lease=30s、poll≈0.2s 的 managed worker runtime
- [x] 3.4 集成 FastAPI lifespan 启停并测试清理、断连不取消和 import-safety

## 4. HTTP API

- [x] 4.1 先编写列表、详情、取消、重试、认证、request-id 与跨 owner API 测试
- [x] 4.2 实现 BackgroundJob Pydantic DTO、service/router 与统一 envelope/error 响应
- [x] 4.3 注册四个路由并用合同测试证明 FastAPI OpenAPI 与共享 manifest 对齐

## 5. 验证与归档

- [x] 5.1 运行 `uv run alembic upgrade head`、backend Ruff、strict Pyright 和 pytest
- [x] 5.2 运行 contracts typecheck/test、`openspec validate --all` 与 `git diff --check`
- [x] 5.3 使用 openspec-verify-change 检查完整性、正确性与一致性并修复所有 CRITICAL、处理 WARNING
- [x] 5.4 同步 delta specs、归档 change，并再次验证归档后 OpenSpec 与 Git 状态
