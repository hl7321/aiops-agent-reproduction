# Design

## Context

报告模型与报告结构校验之间目前存在一处契约缺口：`claims[].claimKey` 在存储层是 `report_evidence_links.claim_key`（`String(120)`，参与唯一约束），在模型层是 `ReportClaimDraft.claim_key`（`max_length=128`），但报告提示词从未定义该字段的语义。模型因此把整句结论写进 `claimKey`，超长后在本地 Pydantic 解析阶段抛错，整份报告被丢弃并进入兜底。

约束：

- 报告的结构校验不能因此整体放宽：证据 ID 必须真实存在、固定中文标题与逐告警编号必须保留。
- 不新增数据库迁移；沿用现有 `claim_key` 存储长度。
- 兜底报告不可被提升为可信报告，这是既有安全边界。

需求见 `specs/aiops-diagnosis-and-evidence/spec.md` 与 `specs/api-and-sse-contracts/spec.md`。

## Goals / Non-Goals

**Goals：**

- 标识长度不再导致整份报告失败，且归一化结果可预测、可测试。
- `claimKey` 的语义在模型可见说明和提示词中明确。
- 客户端能区分"证据不足"与"证据充分但报告生成失败"。

**Non-Goals：**

- 不改变证据充分性判据、报告固定结构或兜底报告内容。
- 不引入新的信任状态取值。
- 不调整结构化输出方式或模型供应商。

## Decisions

### 1. 在 Pydantic 解析前归一化，而不是在校验后补救

在 `ReportClaimDraft.claim_key` 上增加 `mode="before"` 的字段校验器，把超长值按字符截断到存储上限（120）。这样归一化发生在长度约束之前，`with_structured_output` 的解析阶段不会因超长抛错。

备选：在 `validate_report()` 里事后截断。不可行——Pydantic 的错误在解析阶段已经抛出，报告节点拿不到原始对象。

### 2. 归一化后的重名在报告级去重

`validate_report()` 在拿到完整 claims 列表后，按出现顺序维护已用标识集合；重复时追加 `-2`、`-3` 等稳定后缀，并在追加前先缩短基础部分，保证总长度不超过 120。

备选：只在写 link 时去重。不可行——同一 claim 的多条 evidence link 会共享 key，写库时才改写会破坏 claim 分组语义。

### 3. 存储上限沿用 120

以现有 `claim_key` 列为准，把 Pydantic 上限从 128 调整为 120，消除两套数字；不新增 Alembic revision。

备选：把列扩成 `Text` 并去掉上限。虽然能保存整句结论，但 `claim_key` 参与唯一约束、按 key 分组查询，长文本会让索引与语义都变差；结论正文已经在 `markdown` 中，无需重复。

### 4. 用独立错误码表达"报告生成失败"

报告节点保留归一化前的证据评估结果：

- 证据评估为 `verified_evidence`、但报告模型或结构校验失败 → `SYSTEM_AIOPS_REPORT_GENERATION_FAILED`；
- 证据本身不足 → 继续 `SYSTEM_AIOPS_INSUFFICIENT_EVIDENCE`。

兜底报告的信任状态仍为 `insufficient_evidence`，不新增信任状态。

备选：新增 `report_failed` 信任状态。影响面更大（前端、案例提升、既有数据），且本次目标只是让失败原因可区分，因此不采用。

### 5. 字段说明进入模型可见 schema

把 `claimKey` 的 `description` 写成"报告内部短标识，用于把结论与证据关联，不超过 120 字符；不要写整句长段落"。JSON Schema 会自动带上该说明，提示词中同步一句。

备选：删除 `claimKey`、由服务端生成。会丢失模型对"哪些结论属于同一组"的表达能力，暂不采用。

## Risks / Trade-offs

- **截断后两个 claim 语义上变得相同** → 报告级去重追加后缀；每个 claim 的 evidenceIds 仍独立，分组不会合并。
- **截断可能切断中文句子** → 只影响内部标识的可读性，不影响报告正文；提示词同时引导模型写短标识。
- **新增错误码可能在前端显示为未知 code** → 前端按 `failureCode` 透传展示；契约测试保证两端目录一致，必要时补一条展示映射。
- **归一化掩盖了模型不守约束** → 保留 `maxLength` 提示与字段说明；报告分级日志仍可观测报告是否为 fallback。
- **唯一约束在极端情况下仍可能冲突**（同一报告、同一归一化 key、同一 evidence id）→ 去重阶段保证 key 唯一，冲突不会发生。

## Migration Plan

1. 后端与 `packages/api-contracts` 同步新增错误码；
2. 部署顺序无特殊要求（错误码只影响新的诊断任务）；
3. 不回填历史 `claim_key`；
4. 回滚：回退代码即可，无数据迁移。

## Open Questions

（无）
