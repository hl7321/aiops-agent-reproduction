# Tasks

## 1. 时间窗函数

- [x] 1.1 `search_log_window` 增加 `now` 参数；`alerts` 为空时返回 `[now − before, now + after]`，告警分支保持原逻辑
- [x] 1.2 单测覆盖：空 alerts 使用固定 now、单告警、多告警、存在告警但时间不可解析
- [x] 1.3 运行 `test_contracts_and_planning.py` 目标测试

## 2. Runtime 接线

- [x] 2.1 executor 调用 SearchLog 时，用 `_now_ms` 转成 UTC datetime 传给 `search_log_window`
- [x] 2.2 runtime 测试覆盖纯 query（alerts=[]）诊断：SearchLog 参数包含 From/To，且不再出现"没有可用告警"
- [x] 2.3 现有告警诊断测试保持通过；运行 `test_runtime.py`

## 3. 真实 smoke

- [x] 3.1 提交一次纯 query 诊断（alerts=[]），确认任务不再因时间窗输入错误重试
- [x] 3.2 从 diagnostic_steps 读取 SearchLog 参数，确认 From/To 是 `[now−15min, now]` 附近；若日志不在窗口内导致 0 命中，按证据不足如实记录

## 4. 门禁

- [x] 4.1 后端运行 `uv run ruff check .`、`uv run pyright`、`uv run pytest`
- [x] 4.2 运行 `npx --yes @fission-ai/openspec validate fix-aiops-query-only-log-window --strict`

## Workflow follow-up

- [x] 按仓库流程同步 WIKI（`scripts/sync_wiki.py active`），并运行 `npm run docs:build`
- 实现与验证完成后，使用 `openspec-verify-change` 复核，再归档该变更
