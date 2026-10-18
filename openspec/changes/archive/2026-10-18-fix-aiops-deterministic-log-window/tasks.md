# Tasks

## 1. 配置字段

- [x] 1.1 在 `ClsLogUploadSettings` 增加 `windowBeforeMinutes`（默认 15）与 `windowAfterMinutes`（默认 0），校验为非负整数；新增/更新配置测试，确认旧配置不填也能通过
- [x] 1.2 同步 `config/project.template.json` 与 `config/user.project.template.json`，运行配置模板相关测试确认字段存在且默认值一致

## 2. 服务端时间窗注入

- [x] 2.1 扩展 `SearchLogQueryDefaults` 携带窗口偏移，并实现从本轮告警 `startsAt` 计算 `[min−before, max+after]` 的纯函数；单测覆盖单条告警、多条告警与缺时间
- [x] 2.2 在 SearchLog 参数装配中由服务端写入 `From`/`To`，模型提供的同名值被忽略；更新 `normalize_search_log_arguments` 相关测试并通过
- [x] 2.3 在工具 policy 中把 SearchLog 的 `From`/`To` 加入服务端注入字段，新增断言"模型可见 schema 不含 From/To、必填列表也不含"；运行 `test_tool_policy.py` 与 `test_contracts_and_planning.py` 通过
- [x] 2.4 告警缺少或无法解析 `startsAt` 时，在调用工具前以配置类错误失败，并补一条 runtime 测试；运行 `test_runtime.py` 通过（纯函数单测 + runtime 链路覆盖）
- [x] 2.5 更新 `factory.py` 把窗口配置传入 `SearchLogQueryDefaults`，运行相关 factory/runtime 测试通过

## 3. 演示数据与告警脚本

- [x] 3.1 修改 `build_java_cls_records`：十套日志时间落在生成时刻之前的 9 分钟内（T−9 ~ T），套内顺序不变；更新 fixture 测试断言时间范围与顺序
- [x] 3.2 为 `publish_java_ecommerce_alerts.py` 增加 `--starts-at`（带时区 ISO 8601，支持 Z），`endsAt = startsAt + 2h`；非法时间在任何网络请求前失败
- [x] 3.3 更新脚本测试：显式时间、Z 后缀、缺时区拒绝、默认仍为当前时间；运行相关 pytest 通过
- [x] 3.4 增加 `--active-days`（演示用 30 天）与 `--ensure`（已有 10 条活跃告警时跳过发布），并写清 Alertmanager 重启后的补齐方式
- [x] 3.5 增加有效期与 ensure 行为测试，运行脚本测试通过

## 4. 文档与集成验证

- [x] 4.1 更新 README：日志保留期为 30 天，演示顺序为"上传 → 发布告警 → 等待入库 → 诊断"，并说明 `--starts-at`、`--active-days` 与 `--ensure` 的用途
- [x] 4.2 在 `apps/backend` 运行 `uv run ruff check .` 与 `uv run pyright`，两者通过
- [x] 4.3 在 `apps/backend` 运行 `uv run pytest`，全部通过（610 passed）
- [x] 4.4 在仓库根运行 `npm run contracts:typecheck`，契约类型检查通过
- [x] 4.5 真实 smoke：上传一次日志并发布一次告警，连续跑两次诊断，两次都命中真实日志且时间窗一致；任务 `89f298e7`（153 秒 succeeded）与 `24d657a0`（123 秒 succeeded），两次窗口均为 `03:19:11.967Z → 03:34:11.967Z`
- [x] 4.6 运行 `npx --yes @fission-ai/openspec validate fix-aiops-deterministic-log-window --strict`

## Workflow follow-up

- 按仓库流程同步 WIKI（`scripts/sync_wiki.py active`），并运行 `npm run docs:build`
- 实现与验证完成后，使用 `openspec-verify-change` 复核，再归档该变更
