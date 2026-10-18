# 让诊断执行上下文只保留执行所需的信息

## Why

当前 executor 每一步都收到**完整的告警原文**和**全部已持久化证据**。2026-10-18 的抓包量化结果：

- planner 单次 human 内容约 **23.7k 字符**（工具目录约 18.8k + 告警/SOP 上下文约 5.3k）；
- executor 每一步 human 内容约 **6.4k ~ 7.1k 字符**，其中 **4.8k ~ 5.0k** 是重复塞入的完整告警与全部证据；
- report 约 **16.6k 字符**；
- 一次三步诊断里，同一份告警原文和前面的证据会被重复发送多次。

这带来三个问题：

1. **token 成本高**：重复内容不产生新的执行信息，却按每步计费；
2. **职责边界模糊**：executor 只该按计划执行，却拿到了完整的诊断上下文，容易重新"诊断"或改写意图；
3. **模型稳定性**：上下文越长，小模型越容易在工具参数或报告结构上失手。

另外，模型可见的工具目录目前是用 Python `repr` 拼进提示词的（单引号、`None`/`True`），不是标准 JSON；字段投影还丢掉了 `minimum`/`maximum`/`additionalProperties` 等官方约束。

## What Changes

**1. 明确三层上下文。**

- **planner**：保留完整告警、SOP 与完整工具目录——它负责理解和规划。
- **executor**：只保留当前工具说明、整份计划（工具 + 用途）、最小告警摘要、当前步骤真正需要的前序产出、上一次错误。不再传完整 `rawContext`/`fingerprint`/`receivers`，也不再传全部证据。
- **report**：保持现状——它需要全部证据来写报告。

**2. 让计划本身足够执行。**

planner 的每一步用途必须写清执行所需的业务字段（服务名、logger、异常类型、目标信息）；executor 依靠"计划 + 最小摘要 + 工具说明"填参，不再依赖完整告警原文。

**3. 前序产出按需传递。**

executor 只接收当前步骤需要的最近一条前序产出（默认是上一步的产出，限制长度）；SearchLog 的 Query、From/To、Region/TopicId 已由服务端确定性绑定，不再把全部证据重复塞给模型。

**4. 工具目录改为标准 JSON，并保留官方约束。**

- 用 `json.dumps(..., ensure_ascii=False)` 输出工具目录，不再出现 Python `repr`；
- 字段投影保留 `minimum`/`maximum`/`minLength`/`maxLength`/`pattern`/`additionalProperties` 等官方约束；
- Region/TopicId/From/To 等服务端注入字段仍然不出现在模型可见说明中。

非目标：

- 不改变 planner 的完整上下文、不改变 report 的证据输入；
- 不改变工具参数注入、重试分类、报告信任状态；
- 不恢复 `DescribeLogContext`；
- 不切换模型。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: executor 使用最小执行上下文；工具目录使用标准 JSON 并保留官方约束。

## Impact

**后端**

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/runtime.py` | `_step_argument_context` 改为最小执行上下文；按需传递前序产出 |
| `apps/backend/src/super_ai/aiops/planning.py` | planner 提示词要求每步用途自包含；工具目录 JSON 序列化 |
| `apps/backend/src/super_ai/aiops/tool_policy.py` | 字段投影保留官方数值/模式/额外属性约束 |
| `apps/backend/tests/aiops/` | 上下文内容与体积、JSON 解析、约束保留测试 |

**契约与数据**：不改 API、SSE、数据库结构或配置字段。

**测试**：

- executor 上下文不再包含 `rawContext`/`fingerprint`/`receivers`，也不再包含与当前步骤无关的证据；
- executor 仍能完成 DescribeTopics、TextToSearchLogQuery、SearchLog 的现有用例；
- 工具目录可被 `json.loads` 解析，且保留 `minimum`/`maximum`/`additionalProperties`；
- 一次真实诊断的 token 使用量下降（记录前后对比）。
