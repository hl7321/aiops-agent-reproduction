## 1. 准备与基线

- [ ] 1.1 记录实施前基线：后端 `uv run pytest` 通过数、`openspec validate --all` 结果
- [ ] 1.2 复证实测结论：SearchLog 原始返回里 `PkgId`/`PkgLogId` 为空串，且 `incident_id` 一次检索即返回同一链路的连续多行（作为退役依据）

## 2. 退役判定与目录排除

- [ ] 2.1 在语义登记表上增加"数据源不满足前置条件"的退役标记，并写明判定依据
- [ ] 2.2 把 `DescribeLogContext` 标记为退役；`build_aiops_tool_registry` 不再把它放进 registry 与模型可见目录
- [ ] 2.3 确认退役工具与"未登记语义"的工具走不同路径：后者仍可执行、产物落中间产物
- [ ] 2.4 补测试：退役工具不出现在 registry 与目录；未登记语义的只读工具仍然出现

## 3. 计划校验与目录保持一致

- [ ] 3.1 修改 `validate_plan`：只有在上下文工具本轮可用时，`requiresTemporalContext` 才要求对应上下文步骤
- [ ] 3.2 补测试：上下文工具退役时，声明时序需求的计划仍然合法
- [ ] 3.3 补测试：计划引用已退役工具时被拒绝并进入有界纠错

## 4. 提示词说明上下文已在检索结果中

- [ ] 4.1 在 Planner 提示词与可用工具说明中写明：当前链路的日志检索结果本身包含链路顺序信息，证明前后过程使用单次检索即可
- [ ] 4.2 补测试：断言提示词包含该说明，避免退役后模型转向寻找替代工具

## 5. 时序证据判定触发条件

- [ ] 5.1 确认 `requires_temporal_context` 的取值仍来自"计划里是否存在上下文步骤"，工具退役后恒为假
- [ ] 5.2 确认退役后时序分支不再被激活：同一链路的多条有序 log_hit 满足非时序证据规则
- [ ] 5.3 补测试：上下文工具退役 + 多条日志命中时，证据状态为 verified_evidence（不再被虚假判为时序不足）

## 6. 文档化备选方案

- [ ] 6.1 在运维/已知限制文档中记录：退役结论、判定依据、以及"第二次日志检索按链路标识取上下文"的备选方案与启用条件

## 7. 门禁与真实验证

- [ ] 7.1 在 `apps/backend` 运行 `uv run ruff check .`，通过
- [ ] 7.2 在 `apps/backend` 运行 `uv run pyright`，零错误
- [ ] 7.3 在 `apps/backend` 运行 `uv run pytest` 全量，通过
- [ ] 7.4 运行 `openspec validate --all` 与 `git diff --check`，通过
- [ ] 7.5 真实 smoke：先传日志、等入库、重启 Alertmanager 刷新告警时间后再发告警，跑一次完整诊断，核对 Planner 不再规划上下文工具、计划正常通过校验、任务终态与证据状态一致
- [ ] 7.6 把 smoke 结论记入笔记（解决了什么、仍存在什么）

## 8. 归档与文档

- [ ] 8.1 用 `openspec-verify-change` 检查完整性、正确性与设计一致性，修复全部 CRITICAL 问题
- [ ] 8.2 同步 delta specs 到主规格并按 Conventional Commits 提交
- [ ] 8.3 运行 `wiki-sync` 同步 `docs/changes/`，并确认 `npm run docs:build` 通过
- [ ] 8.4 归档变更并更新 Obsidian 笔记：进度总览、当前任务状态、已知问题与待改进
