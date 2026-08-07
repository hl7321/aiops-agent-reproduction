# 安全 Monorepo 基础实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可安装、可运行、可测试且不会把服务端秘密泄露到浏览器的智能 OnCall Agent monorepo 基础。

**Architecture:** 根 npm workspaces 管理 Vue 前端、共享 contracts 和 VitePress 文档，uv 管理采用 `src/super_ai` layout 的 FastAPI 后端。运行期 JSON 配置由后端显式加载，前端构建侧只投影公开 allowlist；所有外部连接都延迟到未来提案通过依赖注入创建。

**Tech Stack:** Python >=3.10、FastAPI、Pydantic v2、uv、hatchling、SQLAlchemy 2 async、aiosqlite、Alembic、pytest、pytest-asyncio、Ruff、strict Pyright；Vue 3.5、Vite 6、TypeScript 5.6、Pinia 3、Vue Router 4、Vitest 2；npm workspaces、VitePress、OpenSpec。

## 全局约束

- 后端包只能位于 `apps/backend/src/super_ai`，只能使用 `from super_ai...`。
- 模块 import 期间不得连接 SQLite、Milvus、LLM 或 MCP。
- pytest 使用 `asyncio_mode=auto`；Ruff 使用 line-length 100、target py310、规则 B/E/F/I/UP；Pyright 使用 strict。
- TypeScript 启用 strict、exactOptionalPropertyTypes、noUncheckedIndexedAccess、isolatedModules、ES2022/Bundler resolution。
- 项目配置只来自本机 JSON 深合并结果，不以 OS 环境变量承载项目配置。
- 浏览器只接收 `frontend.title`、`frontend.apiBaseUrl` 和明确 public 的 analytics key。
- 不实现认证、聊天、知识库、AIOps、MCP、LLM、Milvus 或其他产品功能。
- OpenSpec 文档、README 和项目指南使用简体中文；提交遵循 Conventional Commits。

---

### Task 1: 创建 OpenSpec change 与工程契约

**Files:**
- Create: `openspec/changes/bootstrap-secure-monorepo-foundation/proposal.md`
- Create: `openspec/changes/bootstrap-secure-monorepo-foundation/design.md`
- Create: `openspec/changes/bootstrap-secure-monorepo-foundation/tasks.md`
- Create: `openspec/changes/bootstrap-secure-monorepo-foundation/specs/monorepo-foundation/spec.md`
- Modify: `openspec/config.yaml`
- Create: `AGENTS.md`

**Interfaces:**
- Consumes: 已批准的设计基线。
- Produces: spec-driven change、项目技术栈上下文和所有后续任务的仓库规则。

- [ ] **Step 1: 生成 change 骨架并读取 artifact instructions**

```bash
openspec new change bootstrap-secure-monorepo-foundation
openspec status --change bootstrap-secure-monorepo-foundation --json
```

- [ ] **Step 2: 按 OpenSpec schema 写入简体中文 proposal、design、spec、tasks**

要求 capability 使用 `monorepo-foundation`，spec 以 `## ADDED Requirements` 开始，每个 requirement 至少包含一个 `#### Scenario:`。

- [ ] **Step 3: 写入项目上下文与 AGENTS.md**

明确技术栈、目录、命令、Python import/依赖注入、配置和凭据、tenant 预留、真实 MCP、OpenSpec 简中及桌面 Web 验收规则。

- [ ] **Step 4: 验证 change**

```bash
openspec validate bootstrap-secure-monorepo-foundation --strict
```

预期：exit 0。

### Task 2: 建立根 workspace、contracts 与文档骨架

**Files:**
- Create: `package.json`
- Create: `packages/api-contracts/package.json`
- Create: `packages/api-contracts/tsconfig.json`
- Create: `packages/api-contracts/src/index.ts`
- Create: `packages/api-contracts/src/index.test.ts`
- Create: `packages/api-contracts/README.md`
- Create: `docs/package.json`
- Create: `docs/.vitepress/config.ts`
- Create: `docs/index.md`
- Create: `README.md`

**Interfaces:**
- Produces: `FoundationStatus` typed entrypoint，以及根 `contracts:*`、`frontend:*`、`docs:*` scripts。

- [ ] **Step 1: 先写 contracts 失败测试**

```ts
import { describe, expect, it } from "vitest";
import type { FoundationStatus } from "./index";

describe("FoundationStatus", () => {
  it("表达最小健康状态", () => {
    const status: FoundationStatus = { status: "ok" };
    expect(status.status).toBe("ok");
  });
});
```

- [ ] **Step 2: 运行测试确认入口尚不存在**

```bash
npm run contracts:test
```

预期：因依赖或 `FoundationStatus` 尚未定义而失败。

- [ ] **Step 3: 实现最小类型和 workspace scripts**

```ts
export interface FoundationStatus {
  status: "ok";
}
```

- [ ] **Step 4: 安装并验证 contracts**

```bash
npm install
npm run contracts:typecheck
npm run contracts:test
```

预期：全部 exit 0，并生成根 `package-lock.json`。

### Task 3: 建立后端配置加载与 FastAPI 骨架

**Files:**
- Create: `apps/backend/pyproject.toml`
- Create: `apps/backend/src/super_ai/__init__.py`
- Create: `apps/backend/src/super_ai/app.py`
- Create: `apps/backend/src/super_ai/project_config.py`
- Create: `apps/backend/tests/test_app.py`
- Create: `apps/backend/tests/test_project_config.py`
- Create: `apps/backend/tests/test_import_safety.py`
- Create: `apps/backend/README.md`

**Interfaces:**
- Produces: `create_app() -> FastAPI`、`deep_merge(base, override)`、`load_project_config(project_path, user_path)`。

- [ ] **Step 1: 写配置深合并、health 和 import-safety 失败测试**

```python
def test_deep_merge_preserves_nested_defaults() -> None:
    assert deep_merge({"frontend": {"title": "A", "apiBaseUrl": "/api"}}, {"frontend": {"title": "B"}}) == {
        "frontend": {"title": "B", "apiBaseUrl": "/api"}
    }
```

```python
def test_health() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
```

- [ ] **Step 2: 同步依赖并确认测试失败**

```bash
cd apps/backend
uv sync
uv run pytest
```

预期：因 `super_ai` 实现尚不存在而失败；`uv.lock` 已生成。

- [ ] **Step 3: 实现纯函数配置加载和 app factory**

`deep_merge` 对两个 mapping 递归合并，对标量和数组使用 override；`load_project_config` 只读取显式传入的两个路径。`create_app` 只注册 `/health`。

- [ ] **Step 4: 运行后端局部门禁**

```bash
cd apps/backend
uv run ruff check .
uv run pyright
uv run pytest
```

预期：全部 exit 0。

### Task 4: 建立安全配置模板和忽略边界

**Files:**
- Create: `config/project.template.json`
- Create: `config/user.project.template.json`
- Modify: `.gitignore`
- Create: `tests/test_repository_policy.py`

**Interfaces:**
- Produces: 真实配置文件名、空 secret 模板和可自动验证的仓库安全策略。

- [ ] **Step 1: 写仓库策略失败测试**

测试必须断言模板中所有名称包含 `key`、`secret` 或 `password` 的叶子值为空，并用 `git check-ignore` 验证 `config/project.json`、`config/user.project.json`、`.env.local`、SQLite、日志和构建缓存被忽略。

- [ ] **Step 2: 运行测试确认当前规则不完整**

```bash
cd apps/backend && uv run pytest ../../tests/test_repository_policy.py
```

预期：缺少模板或 ignore pattern，测试失败。

- [ ] **Step 3: 写入模板与完整 `.gitignore`**

模板包含 `frontend`、`analytics.publicKey` 及未来 LLM、CLS、MCP、MinIO 的空凭据区域，但不实现 typed provider。

- [ ] **Step 4: 重跑策略测试**

```bash
cd apps/backend && uv run pytest ../../tests/test_repository_policy.py
```

预期：exit 0。

### Task 5: 建立 Vue 桌面 Web 与 public-config allowlist

**Files:**
- Create: `apps/frontend/package.json`
- Create: `apps/frontend/index.html`
- Create: `apps/frontend/tsconfig.json`
- Create: `apps/frontend/tsconfig.app.json`
- Create: `apps/frontend/vite.config.ts`
- Create: `apps/frontend/src/main.ts`
- Create: `apps/frontend/src/App.vue`
- Create: `apps/frontend/src/router.ts`
- Create: `apps/frontend/src/config.ts`
- Create: `apps/frontend/src/public-config.ts`
- Create: `apps/frontend/src/public-config.test.ts`
- Create: `apps/frontend/src/vite-env.d.ts`
- Create: `apps/frontend/scripts/assert-no-secret.mjs`
- Create: `apps/frontend/README.md`

**Interfaces:**
- Produces: `loadMergedConfig(projectPath, userPath)`、`toPublicConfig(config)`、typed `publicConfig`。

- [ ] **Step 1: 写深合并和 allowlist 失败测试**

测试输入包含 `llm.apiKey = "SENTINEL_SERVER_SECRET"`，断言输出只有 `title`、`apiBaseUrl` 和 `analyticsPublicKey`，序列化结果不包含 sentinel。

- [ ] **Step 2: 运行测试确认失败**

```bash
npm run frontend:test
```

预期：缺少 public-config 实现而失败。

- [ ] **Step 3: 实现 loader、allowlist、Vite define 和最小桌面页**

Vite 只向 `__PUBLIC_CONFIG__` 注入 `toPublicConfig` 返回值；浏览器代码不导入完整 JSON。Vue 页面只显示项目标题和“基础骨架已就绪”。

- [ ] **Step 4: 验证类型、单测和构建**

```bash
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
```

预期：全部 exit 0。

- [ ] **Step 5: 用 sentinel 配置构建并扫描 dist**

```bash
npm run frontend:test:secret
```

脚本在临时目录写入配置、使用显式测试注入构建，并递归扫描 `dist`；发现 `SENTINEL_SERVER_SECRET` 时 exit 1，否则 exit 0。

### Task 6: 建立目录、脚本和基础设施边界测试

**Files:**
- Create: `infra/README.md`
- Create: `scripts/README.md`
- Create: `tests/test_foundation_structure.py`

**Interfaces:**
- Produces: 对最终目录、根 scripts、禁止文件和基础设施边界的可执行断言。

- [ ] **Step 1: 写结构失败测试**

测试断言八个最终目录存在、根 scripts 完整、`apps/backend/app.Dockerfile` 与 `project.compose.json` 不存在，并扫描 Python 源码禁止 `from src.super_ai`。

- [ ] **Step 2: 运行测试并观察缺失项**

```bash
cd apps/backend && uv run pytest ../../tests/test_foundation_structure.py
```

预期：缺少说明或 scripts 时失败。

- [ ] **Step 3: 补齐中文 README 和边界说明**

`infra/README.md` 明确 Compose 最终只包含 etcd、MinIO、Milvus、Attu、Alertmanager；后端、前端、官方 CLS MCP Server 在主机运行。

- [ ] **Step 4: 重跑结构测试**

```bash
cd apps/backend && uv run pytest ../../tests/test_foundation_structure.py
```

预期：exit 0。

### Task 7: 完整验证、同步与归档

**Files:**
- Modify: `openspec/changes/bootstrap-secure-monorepo-foundation/tasks.md`
- Create through archive: `openspec/specs/monorepo-foundation/spec.md`
- Move through archive: `openspec/changes/archive/2026-08-07-bootstrap-secure-monorepo-foundation/`

**Interfaces:**
- Consumes: 所有实现和 delta spec。
- Produces: 全部门禁证据、同步后的主规格和已归档 change。

- [ ] **Step 1: 运行完整门禁**

```bash
openspec validate --all
cd apps/backend && uv run ruff check . && uv run pyright && uv run pytest
cd ../.. && npm run contracts:typecheck && npm run contracts:test
npm run frontend:typecheck && npm run frontend:test && npm run frontend:build && npm run frontend:test:secret
git diff --check
```

预期：全部 exit 0；失败时修复并从受影响门禁开始重跑，最终再完整执行一次。

- [ ] **Step 2: 标记 tasks 完成并重新验证 change**

```bash
openspec validate bootstrap-secure-monorepo-foundation --strict
```

预期：exit 0，tasks 全部为 `[x]`。

- [ ] **Step 3: 同步 delta specs**

按照 `openspec-sync-specs` 将 `monorepo-foundation` delta 合并到主规格并验证。

- [ ] **Step 4: 归档并做最终验证**

```bash
openspec archive bootstrap-secure-monorepo-foundation --yes
openspec validate --all
git status --short
```

预期：change 位于 archive，主规格存在，验证 exit 0，工作区只包含预期未提交改动。
