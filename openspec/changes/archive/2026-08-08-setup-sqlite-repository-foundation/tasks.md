## 1. 配置与持久化原语

- [x] 1.1 先编写失败测试，定义数据库 JSON 深合并、typed validation 与临时路径注入行为
- [x] 1.2 实现 DatabaseSettings、统一 ID、UTC 时间、不可变 record 和确定性 JSON codec
- [x] 1.3 更新可提交配置模板、本机被忽略配置和项目指南，不引入环境变量配置旁路

## 2. SQLAlchemy async 与 Repository 边界

- [x] 2.1 先编写失败测试，定义 Base、UTC/JSON 类型、engine/session factory、并发事务与回滚行为
- [x] 2.2 实现显式 PersistenceRuntime、transaction scope 和 FastAPI session provider，确保资源可关闭
- [x] 2.3 先编写失败的 Repository contract，再实现核心 Protocol 与 extended SQLite 泛型 adapter，确保领域侧不接收 ORM model

## 3. Alembic 迁移权威

- [x] 3.1 先编写 fresh database upgrade、head revision 与 metadata 一致性的失败测试
- [x] 3.2 建立 async Alembic 环境、首个空业务 schema baseline revision 和显式 migration helper
- [x] 3.3 证明运行时代码和应用启动不调用 metadata.create_all 或自动执行迁移

## 4. 导入安全与测试隔离

- [x] 4.1 扩展 import-safety 测试，证明导入 memory/sqlite/extended_sqlite 不创建文件、不连接数据库且不运行迁移
- [x] 4.2 提供基于 pytest tmp_path 的数据库 fixture，证明测试不读取或修改开发者默认 SQLite 文件
- [x] 4.3 更新后端 README 与 AGENTS.md，只说明已实现的 persistence foundation、迁移和验证方式

## 5. 验证与归档

- [x] 5.1 执行 `uv run alembic upgrade head`、pytest、Ruff、strict Pyright、`openspec validate --all` 与 `git diff --check`
- [x] 5.2 使用 openspec-verify-change 核对任务、需求、场景与设计一致性并修复全部 CRITICAL/WARNING
- [x] 5.3 重新运行完整门禁，确认 delta specs 已准备同步归档
