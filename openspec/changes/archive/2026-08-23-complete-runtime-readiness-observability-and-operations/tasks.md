## 1. 合同与测试基线

- [x] 1.1 先扩展 contracts runtime DTO、typed entrypoint、机器可读 paths 与前后端合同 RED 测试
- [x] 1.2 为 health 无副作用、ready 部分失败、config check 阶段区分、MCP 聚焦检查和 metrics 快照编写后端 RED 测试
- [x] 1.3 为 request completion log、递归脱敏、lifecycle allowlist 与 import/启动无副作用编写安全 RED 测试

## 2. 运行时探针与可观测性

- [x] 2.1 实现 runtime Pydantic 模型、可注入 checker 协议和 SQLite/Milvus/Qwen/MCP 最小真实检查
- [x] 2.2 实现 `/ready`、`/config/check`、`/health/mcp` 路由、503 统一失败 envelope 与 app factory 配置路径注入
- [x] 2.3 实现进程内指标 registry、`/metrics` 和 request ID completion middleware
- [x] 2.4 实现通用递归脱敏与安全 lifecycle logger，并接入 indexing、chat、MCP、AIOps 和 background job 的关键状态边界
- [x] 2.5 运行受影响的 backend/contracts 测试、Ruff 与 strict Pyright，修复所有失败

## 3. 本地交付与文档

- [x] 3.1 实现 `scripts/start-local.sh`，覆盖依赖检查、模板复制、五服务 Compose、uv sync、迁移和主机 CLS MCP/FastAPI/Vite 日志
- [x] 3.2 实现不依赖 Bash 的 `scripts/start-local.bat`，保持与 Unix 脚本相同的边界和错误退出语义
- [x] 3.3 更新中文根 README、macOS/Linux/Windows setup、operations monitoring 和真实日志告警教程
- [x] 3.4 删除 app.Dockerfile、project.compose.json、create_compose_app 及所有死引用，并增加行为/治理检查

## 4. 验证、真实链路记录与归档

- [x] 4.1 运行 `openspec validate --all`、contracts typecheck/test、backend Alembic/Ruff/Pyright/pytest、frontend typecheck/test/build、Compose config、Unix 脚本语法和 `git diff --check`
- [x] 4.2 检查 fresh-clone 空模板配置语义，记录 Windows 实机验证与需要真实凭据/目标的桌面链路执行或未执行状态
- [x] 4.3 使用 `openspec-verify-change` 检查 artifacts、实现和测试一致性，修复全部 CRITICAL 并处理 WARNING
- [x] 4.4 同步 delta specs、归档 change，并以 Conventional Commit 提交 main 当前进度
