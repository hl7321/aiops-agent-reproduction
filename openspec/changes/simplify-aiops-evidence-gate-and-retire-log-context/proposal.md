# 简化证据判据并退役日志上下文与指标工具

> 本变更原地取代了先前"把缺失定位字段当作可处理失败"的方案。实测证明那不是"处理失败"的问题：
> 判据要求了一类**当前数据源永远产不出的证据形态**，于是只要模型声明需要时序依据，诊断就必然判证据不足。

## Why

真实运行（任务 `436987e3`，只提交 **1 条**告警）暴露了一条死结。提示词要求"依赖调用顺序、重试、熔断或恢复时用上下文工具查前后日志"，模型照做（它明确写出了"以核对时序信息"），于是：

1. 计划里出现 `DescribeLogContext`；
2. 该工具必填 `Time`/`PkgId`/`PkgLogId`，而 `PkgId` 拿不到，步骤**必然失败**；
3. 计划里存在该步骤 ⇒ `requires_temporal_context` 为真；
4. 判据要求"必须有 `log_context`，或有 ≥2 条命中加指标"——两者都拿不到；
5. ⇒ **必然 `insufficient_evidence`**。

实测事实（三项独立证据）：

| 查证 | 结果 |
|---|---|
| SearchLog 原始返回（绕开本地解析层） | `PkgId: ''`、`PkgLogId: ''`——CLS 服务端返回的空串 |
| 上传 SDK（`tencentcloud-cls-sdk-python`）全量搜索 "pkg" | **零处匹配**——请求、响应、protobuf 都没有这个概念 |
| 上传时显式写 `PkgId` 内容字段后再调用上下文工具 | 服务端不报错，但返回 `LogContextInfos: []`（编的包 ID 找不到包） |

同一次体检还发现：账号内**日志主题 1 个、指标主题 0 个**，指标类工具实测报 `the topic is not metric topic`；
CLS 告警类工具因为本项目告警来自 Alertmanager，只会**静默返回空**（比报错更危险——模型会以为"确实没有告警"）。

**换成单条告警复现，结局完全相同**——所以问题不在"一次处理几条告警"，而在判据要求了一类拿不到的证据。

## What Changes

- **删除判据中的"时序证据"档**。它要求"声明时序 ⇒ 必须有 `log_context`，或有 ≥2 条命中加指标"，而这两类证据在当前数据源上都拿不到，等于把一条规则写成永远无法满足。整档删除。
- **简化判据**：`log_hit` 成为唯一的证据锚点——**只要拿到真实日志命中就算证据充分，一条也算**。去掉"≥2 条命中"与"必须有指标"这类当前数据源无法满足的数量与组合要求；`execution_failed` 与"完全没有证据"两档保留。
- **彻底退役"时序"概念**：删除 `requiresTemporalContext` 输出字段、计划校验中的两条时序规则、以及 runtime 中据此计算 `requires_temporal_context` 的两处调用。该标志当前**唯一**的消费者就是被删除的那条判据。
- **退役日志上下文工具**：`DescribeLogContext` 的必填参数在当前观测链路下永远拿不到，因此在当前数据源退役——不出现在 Planner 可见目录、不进入 registry、不可被规划或调用。
- **退役指标工具**：`QueryMetric` 与 `QueryRangeMetric` 需要指标主题，而账号内没有，同样在当前数据源退役。
- **Planner 提示词改版**：删掉"依赖时序时安排上下文步骤"的指令，改为向 Planner 说明**日志检索结果自带链路顺序**（同一故障链路的日志按发生顺序一起返回），需要证明前后过程时直接依据检索结果，不需要也没有专门工具。

非目标：

- 不换日志上传方式（当前没有可采集的真实日志文件，采集配置路径不在本仓库可控范围），也不伪造 `PkgId`。
- 不改报告固定中文结构与结构校验。
- 不改 attempt 上限、退避策略与其它失败分类。
- 不退役 CLS 告警类与配置类工具（它们只会静默返回空，不阻塞流程），是否一并收窄留待后续。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: 工具可用性必须反映数据源能否满足其前置条件；日志上下文工具与指标工具在当前数据源退役；Planner 可读说明必须说明上下文已在检索结果中；计划校验不再强制"声明时序必须有上下文步骤"。
- `aiops-diagnosis-and-evidence`: 证据充分性判据以 `log_hit` 为唯一锚点，删除无法满足的时序档与数量/组合要求。

## Impact

**后端代码**

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/evidence_policy.py` | 删除时序档与 `requires_temporal_context` 参数；判据简化为"失败且无证据 / 无证据 / 通过"三档 |
| `apps/backend/src/super_ai/aiops/tool_policy.py` | 退役 `DescribeLogContext`、`QueryMetric`、`QueryRangeMetric`；退役依据与数据源能力一起声明 |
| `apps/backend/src/super_ai/aiops/planning.py` | 删除 `PlanDraft` / `ReplanDraft` 的时序字段与 `validate_plan` 的两条时序规则；Planner 提示词改版 |
| `apps/backend/src/super_ai/aiops/runtime.py` | 删除两处 `requires_temporal_context` 计算与传参；上下文与指标装配分支变为不可达 |

**测试**：判据单测按新三档重写；计划校验用例去掉时序场景；新增"单条命中也算证据充分""退役工具不出现在目录""退役工具被规划时计划被拒"；报告节点与 runtime 集成用例同步。

**文档**：记录本次退役结论与依据（上传 API 不产出包 ID、账号无指标主题），并把"第二次日志检索取上下文"写成可追溯的备选方案。

**不再需要的东西**：`requiresTemporalContext` 输出字段、计划校验的两条时序规则、判据里的 `log_context` / `independent_temporal_support` / `non_temporal_support` 分支。
