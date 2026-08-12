# SQLite Repository Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立由 Alembic 管理、可显式注入与关闭、领域侧不依赖 ORM 的 async SQLite persistence foundation。

**Architecture:** `super_ai.memory` 提供配置、不可变 record、Repository Protocol 和通用持久化原语；`super_ai.memory.sqlite` 提供 SQLAlchemy async runtime、类型与迁移 helper；`super_ai.memory.extended_sqlite` 提供后续领域 adapter 可复用的泛型实现。产品 metadata 与首个迁移保持空业务 schema，Repository contract 使用测试专属 model，避免提前实现领域 CRUD。

**Tech Stack:** Python >=3.10、Pydantic v2、SQLAlchemy 2 async、aiosqlite、Alembic、FastAPI lifespan/provider、pytest、pytest-asyncio、Ruff、strict Pyright。

## Global Constraints

- Python 包固定为 `apps/backend/src/super_ai`，只允许 `from super_ai...`。
- 模块 import 期间不得连接或创建 SQLite，不得执行迁移。
- 数据库 URL 只读取本地 `project.json` 与 `user.project.json` 深合并结果，不读取 OS 环境变量。
- Alembic 是 schema 唯一权威，运行期禁止 `metadata.create_all`。
- 领域服务只依赖 Repository Protocol/不可变 record，不接收 ORM model 或 AsyncSession。
- 本 change 不实现认证、Chat、知识、任务、MCP、AIOps、反馈和审计 CRUD。
- 所有测试数据库必须位于 pytest `tmp_path`。

---

### Task 1: Typed 配置与持久化原语

**Files:**
- Create: `apps/backend/src/super_ai/memory/config.py`
- Create: `apps/backend/src/super_ai/memory/records.py`
- Create: `apps/backend/src/super_ai/memory/primitives.py`
- Create: `apps/backend/src/super_ai/memory/__init__.py`
- Modify: `config/project.template.json`
- Test: `apps/backend/tests/memory/test_config.py`
- Test: `apps/backend/tests/memory/test_primitives.py`

**Interfaces:**
- Consumes: `load_project_config(project_path: Path, user_path: Path) -> JsonObject`
- Produces: `DatabaseSettings`, `load_database_settings(...)`, `Record`, `new_id()`, `utc_now()`, `dump_json()` 与 `load_json()`

- [ ] **Step 1: 写入配置与原语失败测试**

```python
def test_user_database_url_overrides_project_url(tmp_path: Path) -> None:
    project_path = write_json(tmp_path / "project.json", {"database": {"url": "sqlite+aiosqlite:///project.db", "echo": False}})
    user_path = write_json(tmp_path / "user.json", {"database": {"url": "sqlite+aiosqlite:///user.db"}})
    settings = load_database_settings(project_path, user_path)
    assert settings.url == "sqlite+aiosqlite:///user.db"
    assert settings.echo is False

def test_json_codec_is_stable_and_rejects_nan() -> None:
    assert dump_json({"b": 2, "a": 1}) == dump_json({"a": 1, "b": 2})
    with pytest.raises(ValueError):
        dump_json({"invalid": float("nan")})
```

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/memory/test_config.py tests/memory/test_primitives.py -v`

Expected: collection fails because `super_ai.memory` APIs do not exist.

- [ ] **Step 3: 实现最小配置与原语**

```python
class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    url: str = Field(min_length=1)
    echo: bool = False

@dataclass(frozen=True, slots=True, kw_only=True)
class Record:
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
```

`dump_json` 使用 `ensure_ascii=False`、`sort_keys=True`、紧凑 separators 与 `allow_nan=False`；`load_database_settings` 只消费显式 JSON 路径。

- [ ] **Step 4: 运行 GREEN**

Run: `cd apps/backend && uv run pytest tests/memory/test_config.py tests/memory/test_primitives.py -v`

Expected: all tests pass.

- [ ] **Step 5: 记录建议提交边界**

```bash
git add apps/backend/src/super_ai/memory config/project.template.json apps/backend/tests/memory
git commit -m "feat(memory): add typed persistence primitives"
```

### Task 2: SQLAlchemy async runtime 与事务

**Files:**
- Create: `apps/backend/src/super_ai/memory/sqlite/base.py`
- Create: `apps/backend/src/super_ai/memory/sqlite/types.py`
- Create: `apps/backend/src/super_ai/memory/sqlite/runtime.py`
- Create: `apps/backend/src/super_ai/memory/sqlite/__init__.py`
- Test: `apps/backend/tests/memory/test_sqlite_runtime.py`

**Interfaces:**
- Consumes: `DatabaseSettings`, `utc_now()`, `dump_json()` 与 `load_json()`
- Produces: `Base`, `IdTimestampMixin`, `UTCDateTime`, `CanonicalJson`, `SessionFactory`, `create_sqlite_engine()`, `create_session_factory()`, `transaction_scope()` 与 `PersistenceRuntime`

- [ ] **Step 1: 写入并发、提交、回滚与关闭失败测试**

```python
async def test_transaction_scope_rolls_back_on_error(session_factory: SessionFactory) -> None:
    with pytest.raises(RuntimeError):
        async with transaction_scope(session_factory) as session:
            session.add(WidgetModel(id="rollback", name="discard"))
            raise RuntimeError("boom")
    async with transaction_scope(session_factory) as session:
        assert await session.get(WidgetModel, "rollback") is None

async def test_concurrent_scopes_use_distinct_sessions(session_factory: SessionFactory) -> None:
    session_ids = await asyncio.gather(write_widget(session_factory, "a"), write_widget(session_factory, "b"))
    assert session_ids[0] != session_ids[1]
```

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/memory/test_sqlite_runtime.py -v`

Expected: import fails because SQLite runtime APIs do not exist.

- [ ] **Step 3: 实现显式资源生命周期**

```python
SessionFactory = async_sessionmaker[AsyncSession]

@asynccontextmanager
async def transaction_scope(factory: SessionFactory) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        async with session.begin():
            yield session

class PersistenceRuntime:
    @classmethod
    def start(cls, settings: DatabaseSettings) -> "PersistenceRuntime": ...
    async def close(self) -> None: ...
```

factory 校验 `sqlite+aiosqlite` driver，并只在调用时构造 engine；连接事件开启 SQLite foreign keys。

- [ ] **Step 4: 运行 GREEN**

Run: `cd apps/backend && uv run pytest tests/memory/test_sqlite_runtime.py -v`

Expected: concurrency, commit, rollback, UTC/JSON round-trip and close tests pass.

- [ ] **Step 5: 记录建议提交边界**

```bash
git add apps/backend/src/super_ai/memory/sqlite apps/backend/tests/memory/test_sqlite_runtime.py
git commit -m "feat(memory): add async sqlite runtime"
```

### Task 3: Repository Protocol 与 SQLite adapter

**Files:**
- Create: `apps/backend/src/super_ai/memory/repository.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/repository.py`
- Create: `apps/backend/src/super_ai/memory/extended_sqlite/__init__.py`
- Test: `apps/backend/tests/memory/test_repository_contract.py`

**Interfaces:**
- Consumes: `Record`, `AsyncSession`, test-only ORM model
- Produces: `Repository[RecordT]` 与 `SqliteRepository[RecordT, ModelT]`；adapter 公开 `add(record)` 和 `get(record_id)`，不公开 ORM model

- [ ] **Step 1: 写入失败的共享合同**

```python
async def repository_contract(repository: Repository[WidgetRecord]) -> None:
    record = WidgetRecord(name="alpha")
    await repository.add(record)
    loaded = await repository.get(record.id)
    assert loaded == record
    with pytest.raises(FrozenInstanceError):
        loaded.name = "changed"  # type: ignore[misc]
```

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/memory/test_repository_contract.py -v`

Expected: Repository and SQLite adapter symbols are missing.

- [ ] **Step 3: 实现最小 Protocol 与 adapter 基类**

```python
class Repository(Protocol[RecordT]):
    async def add(self, record: RecordT) -> None: ...
    async def get(self, record_id: str) -> RecordT | None: ...

class SqliteRepository(Generic[RecordT, ModelT], ABC):
    model_type: type[ModelT]
    @abstractmethod
    def to_model(self, record: RecordT) -> ModelT: ...
    @abstractmethod
    def to_record(self, model: ModelT) -> RecordT: ...
```

`add` 只 flush，`get` 只返回转换后的 record；commit/rollback 仍由外层事务控制。

- [ ] **Step 4: 运行 GREEN**

Run: `cd apps/backend && uv run pytest tests/memory/test_repository_contract.py -v`

Expected: contract passes and no ORM object escapes assertions.

- [ ] **Step 5: 记录建议提交边界**

```bash
git add apps/backend/src/super_ai/memory/repository.py apps/backend/src/super_ai/memory/extended_sqlite apps/backend/tests/memory/test_repository_contract.py
git commit -m "feat(memory): define repository adapter boundary"
```

### Task 4: Alembic baseline 与 migration helper

**Files:**
- Create: `apps/backend/alembic.ini`
- Create: `apps/backend/migrations/env.py`
- Create: `apps/backend/migrations/script.py.mako`
- Create: `apps/backend/migrations/versions/20260808_0001_persistence_foundation.py`
- Create: `apps/backend/src/super_ai/memory/sqlite/migrations.py`
- Test: `apps/backend/tests/memory/test_migrations.py`

**Interfaces:**
- Consumes: `Base.metadata`、本地 JSON database settings 或 Alembic `Config.attributes["database_url"]`
- Produces: `upgrade_database(database_url: str, revision: str = "head") -> None` async helper 与可直接执行的 Alembic CLI 环境

- [ ] **Step 1: 写入 fresh upgrade 与 metadata 一致性失败测试**

```python
async def test_fresh_database_upgrades_to_head(tmp_path: Path) -> None:
    url = sqlite_url(tmp_path / "fresh.sqlite3")
    await upgrade_database(url)
    assert await current_revision(url) == "20260808_0001"

async def test_migrated_schema_matches_metadata(tmp_path: Path) -> None:
    url = sqlite_url(tmp_path / "schema.sqlite3")
    await upgrade_database(url)
    assert await business_table_names(url) == set(Base.metadata.tables)
```

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/memory/test_migrations.py -v`

Expected: migration config/helper files are missing.

- [ ] **Step 3: 实现 async Alembic 环境与空业务 schema revision**

`env.py` 优先读取 `config.attributes["database_url"]`，否则加载仓库内两份本机 JSON；使用 `async_engine_from_config` 与 `connection.run_sync(do_run_migrations)`。baseline 的 `upgrade()`/`downgrade()` 均为空，revision 为 `20260808_0001`。

- [ ] **Step 4: 运行 GREEN**

Run: `cd apps/backend && uv run pytest tests/memory/test_migrations.py -v`

Expected: fresh upgrade reaches head and no business table differs from `Base.metadata`.

- [ ] **Step 5: 记录建议提交边界**

```bash
git add apps/backend/alembic.ini apps/backend/migrations apps/backend/src/super_ai/memory/sqlite/migrations.py apps/backend/tests/memory/test_migrations.py
git commit -m "feat(memory): establish alembic baseline"
```

### Task 5: FastAPI provider、导入安全、指南与最终门禁

**Files:**
- Create: `apps/backend/src/super_ai/memory/sqlite/provider.py`
- Modify: `apps/backend/tests/test_import_safety.py`
- Create: `apps/backend/tests/memory/conftest.py`
- Modify: `apps/backend/README.md`
- Modify: `AGENTS.md`
- Test: `apps/backend/tests/memory/test_import_safety.py`
- Test: `apps/backend/tests/memory/test_provider.py`

**Interfaces:**
- Consumes: `PersistenceRuntime`、FastAPI `Request` 与 pytest `tmp_path`
- Produces: `persistence_lifespan(settings)`、`get_session(request)` 和临时 SQLite fixtures

- [ ] **Step 1: 写入 provider 与 import-safety 失败测试**

```python
def test_importing_memory_does_not_create_sqlite_file(tmp_path: Path) -> None:
    result = run_import_subprocess(tmp_path, "super_ai.memory", "super_ai.memory.sqlite", "super_ai.memory.extended_sqlite")
    assert result.returncode == 0
    assert list(tmp_path.iterdir()) == []

async def test_provider_rejects_closed_runtime() -> None:
    runtime = PersistenceRuntime.start(test_settings())
    await runtime.close()
    with pytest.raises(RuntimeError, match="closed"):
        runtime.session_factory
```

- [ ] **Step 2: 运行 RED**

Run: `cd apps/backend && uv run pytest tests/memory/test_import_safety.py tests/memory/test_provider.py -v`

Expected: provider symbols or closed-runtime guard are missing.

- [ ] **Step 3: 实现 provider 并更新文档**

lifespan 只在进入 context 时 start runtime、在退出时 close；provider 从 `request.app.state.persistence_runtime` 取得 factory。README 与 AGENTS.md 记录 `uv run alembic upgrade head`、迁移唯一权威、Repository/record/normalized schema 和测试隔离规则。

- [ ] **Step 4: 运行完整门禁**

Run:

```bash
cd apps/backend
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest
cd ../..
openspec validate --all
git diff --check
```

Expected: every command exits 0; pytest does not touch `apps/backend/var/memory.sqlite3` except the explicit CLI migration command.

- [ ] **Step 5: 记录建议提交边界**

```bash
git add AGENTS.md apps/backend config/project.template.json docs/superpowers/plans openspec/changes/setup-sqlite-repository-foundation
git commit -m "feat(memory): complete sqlite repository foundation"
```
