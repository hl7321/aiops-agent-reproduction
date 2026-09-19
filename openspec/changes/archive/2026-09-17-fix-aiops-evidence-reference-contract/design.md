## Context

动机见 `proposal.md`。这里只记录现状与约束。

当前状态：

- `packages/api-contracts/src/aiops.ts` 用联合类型 `DiagnosticEvidenceKind` 定义 7 种诊断证据种类。
- `packages/api-contracts/src/sse.ts` 的 `isDiagnosticEvidenceReference` 用一份**手写的 4 项字符串数组**做运行时校验。
- 后端 `apps/backend/src/super_ai/aiops/models.py` 的 `EvidenceKind` 与 TypeScript 类型一致（7 种），生产代码无需修改。
- 现有契约测试只构造 `chat` 频道的 `reference.source`，从未覆盖 `aiops` 频道。

约束：

- TypeScript 的类型在运行时不存在，运行时校验必须依赖真实存在的值。
- 前端与契约包使用 `strict` 与 `exactOptionalPropertyTypes`，改动不能引入 `any`。
- 共享契约是前后端唯一事实来源，不允许在业务代码里复制第二份种类清单。
- 不改动 SSE 事件目录、公共字段与既有 `tool.call` / `task.status` 语义。

## Goals / Non-Goals

**Goals:**

- 让"诊断证据种类"在契约内部只有一份定义，类型与运行时校验同源。
- 让 `aiops` 频道的 `reference.source` 能接受全部合法种类，同时继续拒绝非法种类。
- 用测试锁住这条边界，避免将来新增种类时再次漂移。

**Non-Goals:**

- 不改后端生产代码（后端形状本来就是对的）。
- 不改前端断流策略、"手动重新订阅"交互。
- 不引入新的 SSE 事件类型或字段。

## Decisions

### 决策 1：用导出的常量清单作为类型与校验的共同来源

在 `packages/api-contracts/src/aiops.ts` 导出运行时常量：

- `DIAGNOSTIC_EVIDENCE_KINDS`：`as const` 的只读数组，包含全部诊断证据种类。
- `DiagnosticEvidenceKind`：由该数组派生（`(typeof DIAGNOSTIC_EVIDENCE_KINDS)[number]`），保证类型与清单永远一致。

`sse.ts` 的 guard 改为引用同一数组，不再手写第二份列表。

理由：这是唯一能让"类型"和"运行时校验"不可能漂移的做法。

备选方案与取舍：

- **备选 A：直接把 4 项数组补成 7 项。** 改动最小，但仍然是两份清单，将来新增种类会再次漂移。只在需要热修时才考虑，不作为本变更方案。
- **备选 B：把清单放进 `packages/api-contracts/contract-manifest.json`。** manifest 已经是跨语言对齐的事实来源，但它是构建期数据，前端运行时仍需要一份可导入的常量；对小规模枚举来说，多一层间接不值得。若将来种类清单需要跨语言自动生成，可以在后续变更中迁移。

### 决策 2：后端补齐 `reference.source` 的联合分流（实施中修正）

原计划是"后端只加测试、不改生产代码"。实施时核实发现该判断不成立：

- `apps/backend/src/super_ai/api_contracts.py` 定义了 `DiagnosticReferenceSourceData` 与 `DiagnosticReferenceSourceEvent`，但**这两个类从未被任何代码引用**，也没有进入 `SseEvent` 联合。
- 结果：后端自己的 Pydantic 合同模型**无法表示 aiops 频道的 `reference.source`**，跨语言合同测试必然失败。

这是与前端 guard 同源的漂移：同一个事件形状在契约里有两种描述，只有一种真正生效。

因此改为：

1. 把 `ReferenceSourceData.source` 的类型从 `ReferenceSource` 放宽为 `ReferenceSource | DiagnosticEvidenceReference`，由结构自动分流——chat 形状带 `chunkId`/`rerankScore`，aiops 形状带 `evidenceId`/`kind`，两者互斥，Pydantic 智能联合可正确判定（已实测两种形状都能落到正确模型）。
2. 删除从未被引用的 `DiagnosticReferenceSourceData` 与 `DiagnosticReferenceSourceEvent`，避免同一个事件再次出现"两份描述、只有一份生效"。

理由：保持 `SseEvent` 以 `type` 为判别字段的既有结构不变（`reference.source` 仍然只有一个事件类），改动量最小，且消除了重复描述。

备选方案与取舍：

- **备选：把 `DiagnosticReferenceSourceEvent` 也塞进 `SseEvent` 联合。** 两个类共用 `type: "reference.source"`，同一判别值出现两次，Pydantic 判别联合无法唯一映射，需要在 `channel` 上再加一层判别，复杂度明显上升。
- **备选：按 `channel` 给事件类收窄。** 会牵动 `SseEventBase` 与所有事件类，超出本次修复范围。

后端 `EvidenceKind` 本身已经是完整的 7 种，无需改动；测试仍按原计划遍历它的取值。

### 决策 3：测试分三层，各自证明一件事

- **契约层**：遍历 `DIAGNOSTIC_EVIDENCE_KINDS`，逐项构造 `aiops` 频道的 `reference.source` 事件，断言 guard 通过；再断言未知种类被拒。
- **后端层**：遍历 `EvidenceKind` 的每个取值，断言由它构造的引用形状与共享契约一致，防止后端悄悄多发一种。
- **前端层**：在 transport 层逐种喂入 aiops 的 `reference.source` 帧，断言解析器产出事件而不抛错，并断言未知种类仍被拒绝。

  实施修正：原计划写在 store 层，但核实后发现 **store 只做存储、不做校验**，真正的校验发生在 `sseClient` 的帧解析器里。因此测试改打在解析器上，否则用例会恒真、抓不到本缺陷。

理由：只改 guard 只能证明"契约允许"，还要证明"前端解析器真的会产出事件"；再加一次端到端 smoke 证明"流确实继续走完"。

## Risks / Trade-offs

- **风险：常量数组的类型收窄导致 guard 编译报错。** `as const` 数组的 `includes` 参数会被收窄为字面量联合，直接比较 `string` 需要显式窄化。
  → 缓解：guard 内先用既有的字符串断言收窄，或把数组声明为 `readonly string[]` 后单独导出精确类型；实现时以 `npm run contracts:typecheck` 为准。

- **风险：改动契约常量影响其他调用点。** 目前只有 `sse.ts` 与该类型定义两处使用。
  → 缓解：改动前先全仓检索 `DiagnosticEvidenceKind` 的使用点，确认无遗漏。

- **权衡：本次不做清单的跨语言自动生成。** 后端仍维护自己的 `Literal`，与 TypeScript 清单保持"人工同步 + 测试兜底"。代价是多一处人工同步，收益是不引入代码生成链路。
  → 如果将来证据种类频繁变动，应另立变更把它并入 contract manifest 的生成流程。

## Migration Plan

无数据迁移，无接口兼容性破坏：

1. 契约侧新增常量并切换 guard 引用。
2. 补三层测试。
3. 跑最小门禁。
4. 人工 smoke：重跑一次真实诊断，确认 SSE 不再断流、时间线完整。

回滚策略：本次改动集中在契约包的一个常量与 guard，回退单个提交即可恢复原行为。

## Open Questions

（无）
