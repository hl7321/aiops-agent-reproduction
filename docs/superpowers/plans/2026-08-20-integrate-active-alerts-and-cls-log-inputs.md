# 活跃告警与 CLS 日志输入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 P21 提供真实、标准化、可部分降级的活跃告警输入，并提供只有人工显式运行才写入腾讯 CLS 的安全脚本。

**Architecture:** `super_ai.alerts` 将 typed 配置、provider 解析、并发聚合和认证路由分层；httpx client 仅在请求 dependency 中创建。CLS 是自包含 PEP 723 脚本，纯生成逻辑与延迟 SDK factory 分离，并使用独立 lock 隔离其旧 protobuf/snappy 依赖；FastAPI 永不 import 或调用上传路径。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、httpx、pytest/pytest-asyncio、官方 tencentcloud-cls-sdk-python、TypeScript contracts/OpenAPI manifest。

**Spec:** `openspec/changes/integrate-active-alerts-and-cls-log-inputs/design.md` 与该 change 下两份 delta specs。

## Global Constraints

- 项目配置只读取显式 `project.json` 与 `user.project.json` 深合并结果，不读取 OS 环境变量。
- source 是 deployment-global；认证保护 API，但不创建 user-owned source 或 owner 字段。
- import、测试、app factory、lifespan 和普通启动不得联网或上传 CLS。
- 真实 CLS 写入必须由用户确认自己的 endpoint/topic；自动化只使用 fake HTTP/SDK。
- Python 只允许 `from super_ai...`，Ruff line-length=100、target py310，Pyright strict。

---

### Task 1: Typed 配置与模板

**Files:**
- Create: `apps/backend/src/super_ai/alerts/settings.py`
- Test: `apps/backend/tests/alerts/test_settings.py`
- Modify: `config/project.template.json`
- Modify: `config/user.project.template.json`

**Interfaces:**
- Produces: `AlertSourceSettings`, `PrometheusAlertsSettings`, `ClsLogUploadSettings`；`load_alert_settings(project, user)` 与 `load_cls_log_upload_settings(project, user)`。

- [ ] **Step 1: 写配置失败测试**：用临时 JSON 构造两个合法 source，并分别证明重复 name、userinfo URL、timeout=0、Basic Auth 单边填写、CLS 非 HTTPS endpoint 在 client 创建前失败。
- [ ] **Step 2: 运行 RED**：`cd apps/backend && uv run pytest tests/alerts/test_settings.py -q`，预期因 `super_ai.alerts.settings` 不存在失败。
- [ ] **Step 3: 最小实现**：使用 frozen Pydantic 判别联合；配置错误统一包装为不含原值的 `ProjectConfigError("prometheusAlerts 配置校验失败")` 或 `ProjectConfigError("clsLogUpload 配置校验失败")`。
- [ ] **Step 4: 更新模板**：把旧单 baseUrl 改为 sources，增加 CLS `logsetId`，所有 password/secret 保持空。
- [ ] **Step 5: 运行 GREEN**：定向 pytest、Ruff、Pyright 均通过。

### Task 2: 共享合同

**Files:**
- Create: `packages/api-contracts/src/alerts.ts`
- Create: `packages/api-contracts/src/alerts.test.ts`
- Modify: `packages/api-contracts/src/index.ts`
- Modify: `packages/api-contracts/contract-manifest.json`
- Modify: `apps/backend/src/super_ai/api_contracts.py`
- Modify: `apps/backend/tests/test_contract_manifest.py`

**Interfaces:**
- Produces: `AlertSourceType`, `ActiveAlertStatus`, `AlertSource`, `ActiveAlert`, `ActiveAlertsData` 和 OpenAPI operation `getActiveAlerts`。

- [ ] **Step 1: 写合同 RED**：以手写完整 DTO 断言 nullable service/severity、source/rawContext；断言错误码 503 与 bearer path 401/403/503。
- [ ] **Step 2: 运行 RED**：`npm run contracts:test` 与 backend manifest 定向测试必须因缺少合同失败。
- [ ] **Step 3: 最小实现**：同步 manifest、TS exports、Pydantic alias 与错误目录，不引入 providerStatuses。
- [ ] **Step 4: 运行 GREEN**：contracts typecheck/test 与 backend manifest 测试通过。

### Task 3: Provider 与 Aggregator

**Files:**
- Create: `apps/backend/src/super_ai/alerts/models.py`
- Create: `apps/backend/src/super_ai/alerts/providers.py`
- Create: `apps/backend/src/super_ai/alerts/service.py`
- Test: `apps/backend/tests/alerts/test_providers.py`
- Test: `apps/backend/tests/alerts/test_aggregator.py`

**Interfaces:**
- Produces: `AlertProvider` Protocol、`PrometheusV1AlertProvider`、`AlertmanagerV2AlertProvider`、`AlertAggregator.list_active()`。

- [ ] **Step 1: 写 Prometheus RED**：fake transport 返回官方完整 payload，手写期望 activeAt→startsAt、firing 与 rawContext；另测非 JSON/错误响应脱敏。
- [ ] **Step 2: 实现 Prometheus provider 并运行 GREEN**。
- [ ] **Step 3: 写 Alertmanager RED**：覆盖 active→firing、suppressed、不合法 state 与 `/api/v2/alerts` 请求参数。
- [ ] **Step 4: 实现 Alertmanager provider 并运行 GREEN**。
- [ ] **Step 5: 写 Aggregator RED**：用带 asyncio.Event 的 provider 证明并发；覆盖部分失败、成功空数组、全失败/零源 503 与稳定排序。
- [ ] **Step 6: 实现 Aggregator 并运行全部 alerts 测试 GREEN**。

### Task 4: 认证 API 与运行期注入

**Files:**
- Create: `apps/backend/src/super_ai/alerts/dependencies.py`
- Create: `apps/backend/src/super_ai/alerts/router.py`
- Modify: `apps/backend/src/super_ai/app.py`
- Test: `apps/backend/tests/alerts/test_api.py`
- Test: `apps/backend/tests/alerts/test_import_safety.py`

**Interfaces:**
- Consumes: Task 1 settings、Task 2 DTO、Task 3 aggregator。
- Produces: `GET /aiops/alerts/active` 与 request-scoped provider/client lifecycle。

- [ ] **Step 1: 写 API RED**：构造临时 SQLite 认证 app；未认证断言 401 且 provider 调用数为 0，认证成功断言 items-only envelope，全失败断言 503。
- [ ] **Step 2: 最小路由/依赖实现**：先依赖 `CurrentUser`，再从 `app.state.alert_settings` 建 provider；httpx client 由 async dependency 关闭。
- [ ] **Step 3: 注入 app factory**：`create_app(alert_settings=...)` 只保存 typed settings，`create_configured_app` 显式加载，不发请求。
- [ ] **Step 4: import-safety GREEN**：patch client 构造/网络/CLS SDK 为失败，import 与 app 创建仍通过；运行 alerts 与 app 定向测试。

### Task 5: CLS 显式上传脚本

**Files:**
- Create: `scripts/generate_and_upload_cls_logs.py`
- Create: `apps/backend/tests/scripts/test_generate_and_upload_cls_logs.py`
- Create: `scripts/generate_and_upload_cls_logs.py.lock`
- Modify: `scripts/README.md`

**Interfaces:**
- Consumes: `ClsLogUploadSettings` 与官方 `LogClient`/`LogGroupList`。
- Produces: `generate_log_records(settings, count)`、`build_log_group_list(records)`、`upload_logs(settings, count, client_factory)`、CLI `main()`。

- [ ] **Step 1: 依赖锁定**：脚本 PEP 723 声明 `tencentcloud-cls-sdk-python==1.0.4`，运行 `uv lock --script scripts/generate_and_upload_cls_logs.py` 生成隔离 lock；backend pyproject/uv.lock 不变。
- [ ] **Step 2: 写脚本 RED**：import 不调用 SDK；count 0/101、endpoint 非 HTTPS、缺凭据在 factory 前失败。
- [ ] **Step 3: 写 payload RED**：count=3 恰好生成三条，字段目录固定、message 有界、region 每条存在、序列化内容不含 secret/password/token。
- [ ] **Step 4: 实现纯生成与 protobuf 构造并运行 GREEN**。
- [ ] **Step 5: 写上传 RED**：fake factory 捕获 endpoint/secret；fake client 捕获 topic/groups，断言一次调用且 logsetId 未传入；异常含 secret 时只见 `[redacted]`。
- [ ] **Step 6: 实现延迟 SDK factory/CLI**：只有 `main→upload_logs→default_client_factory` 才 import SDK 并写入；stdout 只输出 count/requestId。
- [ ] **Step 7: 文档与 GREEN**：说明真实副作用和确认流程，运行脚本定向测试、Ruff、Pyright。

### Task 6: 完整验证、规格同步与归档

**Files:**
- Modify: `openspec/changes/integrate-active-alerts-and-cls-log-inputs/tasks.md`
- Modify/Create: `openspec/specs/active-alert-and-cls-log-inputs/spec.md`
- Modify: `openspec/specs/api-and-sse-contracts/spec.md`

**Interfaces:**
- Produces: 可归档、无 CRITICAL/WARNING 的 P20。

- [ ] **Step 1: 完整门禁**：backend `uv run ruff check . && uv run pyright && uv run pytest`；contracts typecheck/test；`openspec validate --all`；`git diff --check`。
- [ ] **Step 2: 外部 smoke 判断**：可用的真实 Prometheus/Alertmanager 只读目标可执行并如实记录；没有用户针对 CLS endpoint/topic 的确认时明确记为未执行，绝不上传。
- [ ] **Step 3: OpenSpec verify**：逐项映射 requirements/scenarios/design；修复全部 CRITICAL/WARNING 后重跑受影响门禁。
- [ ] **Step 4: 同步与归档**：智能合并两份 delta spec，`openspec validate --specs` 后移动到 `openspec/changes/archive/2026-08-20-integrate-active-alerts-and-cls-log-inputs`。
