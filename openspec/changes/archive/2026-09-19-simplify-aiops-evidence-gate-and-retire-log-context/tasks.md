## 1. 准备与基线

- [x] 1.1 记录实施前基线：后端 `uv run pytest` 通过数、`openspec validate --all` 结果
- [x] 1.2 固化实测依据：SearchLog 原始返回 `PkgId`/`PkgLogId` 为空、上传 SDK 无 pkg 概念、账号内日志主题 1 个且指标主题 0 个（写进文档）
- [x] 1.3 记录对照：十条告警与单条告警两种输入下，判据都因时序档落到 `insufficient_evidence`

## 2. 判据简化（先定"要什么"）

- [x] 2.1 把 `evaluate_claim_evidence` 简化为三档：执行失败 / 无 `log_hit` / 至少一条 `log_hit`
- [x] 2.2 删除时序档、`contexts`、`independent_temporal_support`、`non_temporal_support` 中间量
- [x] 2.3 从函数签名删除 `requires_temporal_context` 参数
- [x] 2.4 补测试：单条命中即 `verified_evidence`；无命中为 `insufficient_evidence`；检索真失败且无命中为 `execution_failed`；空结果不算执行失败

## 3. 清理调用方（谁传的）

- [x] 3.1 删除 runtime 中两处 `requires_temporal_context` 的计算与传参（replanner 与 report 节点）
- [x] 3.2 确认删除后不再有任何地方读取"计划里是否存在上下文步骤"
- [x] 3.3 补测试：报告节点在只有日志命中、无上下文产物时判 `verified_evidence`

## 4. 计划校验与提示词（谁产生与校验的）

- [x] 4.1 `validate_plan` 删除两条时序规则（声明时序必须有上下文步骤 / 未声明不得有）
- [x] 4.2 删除 `PlanDraft` 与 `ReplanDraft` 的 `requiresTemporalContext` 字段
- [x] 4.3 Planner 提示词改版：删除"依赖时序时安排上下文步骤"的硬性约束；新增事实说明"日志检索结果自带链路顺序，需要证明前后过程时直接依据检索结果，不需要也没有专门工具"；输出结果段删除时序字段
- [x] 4.4 补测试：计划不再包含时序字段；含退役工具的计划被拒；退役工具可用时计划仍合法

## 5. 退役工具（没用了）

- [x] 5.1 在语义登记表增加"数据源不满足前置条件"的退役标记，并写明依据
- [x] 5.2 退役 `DescribeLogContext`（必填的包 ID 在当前上传链路下永远为空）
- [x] 5.3 退役 `QueryMetric` 与 `QueryRangeMetric`（需要指标主题，当前账号没有）
- [x] 5.4 确认 registry 与模型可见目录都不再出现这三个工具
- [x] 5.5 补测试：退役工具不在目录/registry；未登记语义的只读工具仍按原路径处理

## 6. 清理可达性变差的分支

- [x] 6.1 确认 executor 的 log_context 装配与指标装配分支变为不可达，按最小改动原则处理（删除或显式保留说明）
- [x] 6.2 确认 `log_context` 证据类型保留（历史记录仍可读），只是不再产生新数据
- [x] 6.3 删除报告节点"claims 必须引用全部支撑证据、否则降级"的隐藏门槛（实测 8 条命中只引用 6 条即被误判证据不足；规格只要求关键结论有真实链接）
- [x] 6.4 把集成测试的报告替身改为"只引用其中一条证据"，用更强的用例锁住放宽后的行为

## 7. 文档

- [x] 7.1 记录退役结论、判定依据与已验证过程
- [x] 7.2 把"第二次日志检索按链路标识取上下文"写成备选方案，注明启用条件（数据源变化时才考虑）

## 8. 门禁与真实验证

- [x] 8.1 在 `apps/backend` 运行 `uv run ruff check .`，通过
- [x] 8.2 在 `apps/backend` 运行 `uv run pyright`，零错误
- [x] 8.3 在 `apps/backend` 运行 `uv run pytest` 全量，通过
- [x] 8.4 运行 `openspec validate --all` 与 `git diff --check`，通过
- [x] 8.5 真实 smoke：先传日志、等入库、重启 Alertmanager 刷新告警时间后再发告警，跑一次完整诊断，核对"计划不再出现上下文工具""单条日志命中即判证据充分""任务终态与信任状态一致"
- [x] 8.6 把 smoke 结论记入笔记（解决了什么、仍存在什么）

## 9. 归档与文档

- [x] 9.1 用 `openspec-verify-change` 检查完整性、正确性与设计一致性，修复全部 CRITICAL 问题
- [x] 9.2 同步 delta specs 到主规格并按 Conventional Commits 提交
- [x] 9.3 运行 `wiki-sync` 同步 `docs/changes/`，并确认 `npm run docs:build` 通过
- [x] 9.4 归档变更并更新 Obsidian 笔记：进度总览、当前任务状态、已知问题与待改进
