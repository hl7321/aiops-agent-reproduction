# 让诊断报告不再因 claim 长度被整份判失败

## Why

2026-10-16 实机连续跑了两轮诊断（任务 `cf0a3656`、`acba86e0`），两次都是**三个工具全部成功、真实日志命中 4 条**，最终却以 `failed` 收场，失败码是 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`。抓包和数据库确认，真正的原因与证据无关：

1. 模型交回的 `claims[].claimKey` 有三条分别是 198、162、146 个中文字；
2. 代码里的 `ReportClaimDraft.claim_key` 限制 `max_length=128`，而 `report_evidence_links.claim_key` 的存储列只有 `String(120)`；
3. 提示词只解释了 `claims[].evidenceIds`，**从未解释 `claimKey` 是什么**，模型自然地把它当成"结论正文"来写；
4. 发给模型的 JSON Schema 虽然带了 `maxLength`，但服务端不强制，长度校验在本地 Pydantic 解析时才爆炸；
5. 异常被报告节点的 `try/except` 兜住，整份报告被丢弃、改走兜底报告；兜底报告按既有规则一律降级为 `insufficient_evidence`；
6. 于是用户看到"证据不足"，但真实情况是**证据充足、报告结构没通过**。

这条路径不是偶发：当天连跑两次都是同一个死法，另一次成功（`197c4df6`）只是模型恰好把 `claimKey` 写短了。**当前演示能否成功取决于模型的手气**，必须修。

另外，失败码把两种完全不同的情况混在一起：一种是"日志确实没查到，证据不足"，另一种是"证据够，但报告生成失败"。用户和前端无法区分，后续案例沉淀与问题排查也都会被误导。

## What Changes

**1. 明确 `claimKey` 的语义，并让它不再触发硬失败。**

- `claimKey` 是**报告内部用来把结论与证据关联起来的短标识**，不是结论正文；在模型可见的字段说明和报告提示词中明确写出这一定义与长度建议。
- 服务端对超长取值做**确定性归一化**（按存储上限截断），不再让长度问题导致整份报告被丢弃。
- 同一份报告内若归一化后出现重复标识，服务端追加稳定后缀去重，避免 `report_evidence_links` 的唯一约束冲突。
- 模型契约与存储契约对齐：以现有 `claim_key` 列长度为准，避免 128 与 120 两套数字并存。

**2. 保留其余报告校验的严格性。**

证据 ID 必须真实存在、固定中文标题与逐告警编号必须齐全、`evidenceIds` 不能为空——这些规则不变，**只有"标识长度"从硬失败改为归一化**。

**3. 区分"报告生成失败"与"证据不足"。**

- 新增稳定错误码 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`。
- 当本轮证据评估为 `verified_evidence`、但报告模型调用或结构校验失败并走兜底时，任务使用该错误码收尾。
- 当本轮确实没有足够的真实证据时，继续使用既有的 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`。
- 兜底报告的信任状态仍是 `insufficient_evidence`，**不会因为换了错误码而被提升**。

非目标：

- 不改变报告固定中文结构、证据充分性判据与兜底报告的内容规则。
- 不改变模型选择或结构化输出方式（`json_schema` 保持现状）。
- 不涉及日志时间窗、From/To 注入、上下文瘦身、工具目录序列化或 DeepSeek 切换。
- 不新增数据库迁移；沿用现有 `claim_key` 列长度。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `aiops-diagnosis-and-evidence`: 明确 claim 标识契约；超长标识归一化而非整份失败；报告生成失败与证据不足使用不同失败语义，且兜底报告不得被提升。
- `api-and-sse-contracts`: 稳定错误目录新增 `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`，并保持 Pydantic、TypeScript 与前端展示一致。

## Impact

**后端行为**

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/aiops/planning.py` | 补充 `claimKey` 字段说明；对超长值做解析前归一化 |
| `apps/backend/src/super_ai/aiops/reporting.py` | 校验阶段对 claim 标识去重；其余结构规则保持不变 |
| `apps/backend/src/super_ai/aiops/runtime.py` | 兜底报告按"证据是否原本充分"选择失败码 |
| `apps/backend/src/super_ai/api_contracts.py` | 新增错误码与默认消息 |
| `packages/api-contracts/src/` | 同步 TypeScript 错误目录与契约测试 |

**契约与前端**：新增一个任务失败码；`diagnostic_tasks.status` 与三个信任状态的取值不变。前端按既有 `failureCode` 展示逻辑即可区分两类失败，不需要新的 SSE 事件类型。

**数据**：不新增迁移，不改表结构；超长 `claimKey` 在入库前被归一化。

**测试**：

- 报告模型输出含超长 `claimKey` 时，任务仍能生成模型报告并成功；
- 同一报告内多个 claim 归一化后重名时，证据链接不冲突；
- 引用不存在证据 ID、缺少固定标题等仍然失败并走兜底；
- 证据充分但报告失败 → `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`；
- 证据确实不足 → 仍为 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`；
- 后端与 TypeScript 错误目录保持同一份 code 集合。
