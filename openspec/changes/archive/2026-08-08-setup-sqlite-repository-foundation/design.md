## Context

参见 `proposal.md` 的动机与 `specs/sqlite-repository-foundation/spec.md` 的行为合同。当前后端已经锁定 SQLAlchemy 2 async、aiosqlite 与 Alembic 依赖，但尚无 ORM metadata、engine/session 生命周期、迁移环境或 Repository 边界。现有配置加载器只负责 JSON 深合并，FastAPI app factory 导入和 `/health` 均不访问外部服务。

本设计必须维持 Python >=3.10、`src` layout、`from super_ai...`、strict Pyright、`asyncio_mode=auto` 与模块导入零 I/O 的基线。数据库 URL 仅来自本地 JSON 合并配置，不增加环境变量旁路。

## Goals / Non-Goals

**Goals:**

- 建立可以由 FastAPI lifespan、依赖 provider 或测试显式创建和释放的 async persistence runtime。
- 让 Alembic 与 SQLAlchemy metadata 从同一个 `Base` 取得 schema 定义，同时保持迁移为唯一建表路径。
- 让领域代码面向 Repository Protocol 与不可变 record，隔离 ORM 与数据库厂商。
- 固化 ID、UTC 时间、JSON codec、事务 scope 和临时数据库测试约定。

**Non-Goals:**

- 不实现认证、Chat、知识、任务、MCP、AIOps、反馈或审计表与 CRUD。
- 不在应用启动时自动运行迁移，不用 `metadata.create_all` 管理生产 schema。
- 不引入 PostgreSQL 驱动、同步 SQLAlchemy API、应用容器或 Compose 数据库服务。
- 不为尚未出现的领域查询设计通用 JSON document store 或万能 repository。

## Decisions

### 1. 核心合同、SQLite 基础与扩展 adapter 分层

`super_ai.memory` 只导出不可变 `Record`、泛型 `Repository` Protocol、ID/UTC/JSON 原语和配置类型；它不导入具体数据库实现。`super_ai.memory.sqlite` 包含 `Base`、公共 ORM mixin、engine/session/runtime 和 migration helper；`super_ai.memory.extended_sqlite` 包含供后续具体领域 adapter 继承的泛型 SQLite repository 基类。领域服务只能依赖核心 Protocol，具体 adapter 内部才接触 ORM model 和 `AsyncSession`。

备选方案是让领域服务直接接收 SQLAlchemy repository 或 session。该方案代码更少，但会把 ORM 生命周期、查询 API 和 SQLite 特性泄露到业务层，未来切换 PostgreSQL或编写纯内存 contract tests 时需要重写服务，因此不采用。

### 2. 空业务 schema 的 Alembic baseline

首个 revision 建立迁移链基线但不创建产品表；fresh upgrade 只产生 Alembic 自身的版本表。应用 `Base.metadata` 同样不含领域表，schema 一致性检查忽略 `alembic_version` 后应为空。后续每个领域 change 同时新增规范化 ORM model 与 Alembic revision。

备选方案是创建通用 key/value 或 JSON records 表用于演示 Repository。它会诱导后续业务状态进入无结构 JSON，并违反本阶段不提前实现领域 CRUD 的边界，因此 contract tests 使用测试专属 metadata、model 和 record，不污染产品迁移。

### 3. engine 和 session 由显式 runtime 管理

`create_sqlite_engine(settings)` 与 `create_session_factory(engine)` 只在被调用时创建资源。`PersistenceRuntime.start(settings)` 负责构造 engine/session factory，`close()` 负责 dispose；FastAPI 可通过 lifespan 持有 runtime，依赖 provider 从 `app.state` 取得 factory。测试和迁移 helper 可走显式初始化路径。模块级只存在类、函数和 metadata，不存在 engine、sessionmaker 实例、文件探测或迁移调用。

备选方案是在模块导入时创建全局 engine。它使用方便，但测试无法可靠注入临时 URL，import 会触发连接池/文件副作用，并使关闭责任不明确，因此不采用。

### 4. JSON 深合并后进行 typed database validation

沿用 `project_config.py`：先读取 `project.json`，再以 `user.project.json` 递归覆盖。`DatabaseSettings` 只验证合并结果中的 `database.url`、`database.echo` 等数据库字段。SQLite factory 使用 SQLAlchemy URL parser 验证 `sqlite+aiosqlite` driver；迁移 env 默认解析仓库内两份本机 JSON，也允许测试通过 Alembic `Config.attributes` 显式注入临时 URL。该注入不是 OS 环境变量，也不会读取开发者真实值。

备选方案是使用 `DATABASE_URL` 环境变量或把 URL 固定到 `alembic.ini`。两者都会产生第二配置来源，与项目安全配置边界冲突，因此不采用。

### 5. 事务由 context manager 决定提交与回滚

`transaction_scope(session_factory)` 每次创建独立 `AsyncSession`，使用 `session.begin()` 在正常退出时提交、异常时回滚，并始终关闭 session。Repository 方法执行 `add/get/flush`，不自行 commit；事务所有权保持在 service/unit-of-work 边界。SQLite engine 在连接时开启 foreign key，并为临时文件数据库使用标准 async pool，使并发 session 真实经过不同 session 对象。

备选方案是 repository 每个方法自动 commit。它无法把多个写操作组成原子事务，错误恢复也难以预测，因此不采用。

### 6. 统一 record、ID、UTC 与 JSON 表示

基础 `Record` 使用 `frozen=True, slots=True`，包含字符串 ID 与 UTC `created_at/updated_at`。ID 使用无共享状态的 UUID4 hex；时间使用兼容 Python 3.10 的 `datetime.now(timezone.utc)`。JSON codec 使用 UTF-8 友好的紧凑、排序 key 编码，并拒绝 NaN/Infinity；SQLite JSON type 通过该 codec 存储。只有无需查询内部成员的附属值才能使用 JSON，需要过滤、唯一性、关联或外键的数据必须成为规范化列/表。

备选方案是依赖 SQLite 默认 JSON 文本、naive datetime 或自增整数 ID。它们会造成跨 adapter 表示差异、时区歧义或 ID 分配耦合，因此不采用。

### 7. 测试 helper 与产品数据库严格隔离

pytest fixture 从 `tmp_path` 生成 `sqlite+aiosqlite` 文件 URL；`upgrade_database(url)` 通过 Alembic `Config.attributes` 把 URL传入迁移线程。Repository contract 使用测试专属 DeclarativeBase/model 和临时数据库，测试不加载仓库本机配置。CLI 验收 `uv run alembic upgrade head` 则显式使用被忽略的本机 JSON；模板提供默认本机路径但不包含凭据。

备选方案是在测试中使用 `apps/backend/var/memory.sqlite3` 或共享内存连接。前者会污染开发者数据，后者难以真实验证并发连接与迁移文件路径，因此不采用。

## Risks / Trade-offs

- [空 baseline 不展示真实业务表迁移] → 通过检查 head revision、metadata 一致性和后续 change 必须成对新增 model/revision 来验证迁移链，同时避免提前设计领域 schema。
- [SQLite 并发写入能力有限] → 当前测试只验证独立 async session 与短事务；repository 边界允许未来替换 PostgreSQL，不在本阶段引入复杂锁策略。
- [泛型 repository 基类可能不适合复杂查询] → 只提供最小 add/get 基础；后续领域定义专用 Protocol 和规范化查询，不扩展万能查询 DSL。
- [Alembic async env 内部需要同步桥接] → 使用官方 async engine + `run_sync` 模式，测试 helper 在线程中执行 CLI command，避免嵌套 event loop。
- [SQLite datetime 可能丢失原始 tzinfo] → 自定义 UTC type 在写入时归一化、读取时恢复 UTC；contract test 覆盖往返。

## Migration Plan

1. 更新配置模板并为当前被忽略的本机配置补充 `database.url`。
2. 加入 memory 核心合同、SQLite runtime、Alembic 环境和空业务 schema baseline revision。
3. 使用临时数据库执行 migration 与 repository contract 测试；确认应用 import 和 `/health` 不触发数据库。
4. 在本机 JSON 指向的 SQLite 路径执行 `uv run alembic upgrade head`，验证 CLI 可到达 head。

回滚时使用 `uv run alembic downgrade base` 只移除 Alembic revision 标记；本 revision 不包含产品表或数据。若实施尚未发布，可删除本 change 新增代码与 revision，不需要数据迁移或 force push。
