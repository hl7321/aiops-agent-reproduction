# Design

## Context

见 `proposal.md - Why`。当前 Planner 与 Report 共用 `_model_context()`，该函数只拼装告警、SOP 状态、计划、步骤与证据，没有 `task.query`。知识检索虽然使用 query，但结果只是间接证据；SOP 缺失或不相关时，Planner 没有可靠的用户目标。

行为要求见 `specs/aiops-diagnosis-and-evidence/spec.md` 与 `specs/schema-aware-aiops-tool-execution/spec.md`。

## Goals / Non-Goals

**Goals：**

- Planner 直接、稳定地获得规范化后的非空 query；
- 明确 query、告警与 SOP 的职责和优先级；
- 保持 Executor 的最小上下文，不传完整对话、全部 SOP 或全部证据；
- 用可注入 fake model/knowledge 的测试证明 query 不再依赖 SOP。

**Non-Goals：**

- 不修改诊断 API、共享 DTO、SSE、SQLite 或前端；
- 不修改 SearchLog 时间窗、query-builder 或工具参数来源；
- 不修改 Report 的上下文范围；
- 不把 query 写入结构化运行日志。

## Decisions

### 1. Planner 上下文增加独立 `query` 输入

`_model_context()` 增加可选 `query` 参数，并只在 Planner 调用时传入 `task.query`。输出使用独立标签：

```text
用户问题：<query 或“未提供”>
告警：<alerts>
...
```

不把 query 拼进告警 JSON，也不依赖 SOP 摘要传递，原因是两者语义不同，混在一起会让模型无法判断哪部分是用户目标、哪部分是检索结果。

备选：只把 query 加入知识检索文本。该方案已存在且不足，因为 SOP 为空时 Planner 仍看不到 query。

### 2. 在 Planner 提示词中声明输入优先级

Planner 系统提示明确：

- 有 query：query 定义诊断目标，告警补充对象、时间与上下文，SOP 只提供辅助经验；
- 没有 query：告警定义诊断目标；
- query 与 SOP 不一致：保留 query，不擅自切换为 SOP 中的另一类故障；
- query 是用户问题数据，不得借 query 扩大工具、owner 或参数权限。

备选：只把 query 放进上下文，不改提示词。模型可能继续因为系统提示“面前有一条告警”而忽略纯 query，因此不足。

### 3. Executor 继续使用最小上下文

Planner 负责把 query 的关键对象写入步骤用途；Executor 继续只接收当前工具说明、整份计划、最小告警摘要和当前步骤所需前序产出。这样 query 的“理解与计划”发生在 Planner，执行阶段不重复塞完整用户输入或 SOP。

备选：把原始 query 直接传给每一步 Executor。该方案违反上下文裁剪目标，也会让无关步骤获得不需要的信息。

### 4. 回归测试以“无 SOP 纯 query”为主

关键测试让 knowledge 返回空、alerts 为空、query 非空，fake Planner 明确断言上下文中出现 query。另测 query+SOP 冲突和仅告警场景，防止修复时打乱既有优先级。

## Risks / Trade-offs

- **用户 query 可能包含提示注入内容** → 在系统提示中把 query 定义为问题数据，不得扩大权限；工具目录、owner scope 和参数注入规则仍由代码约束。
- **Planner 上下文略增** → query 受 API 的 4000 字符上限约束，且不传完整对话或其他证据，增量有界。
- **Executor 可能丢掉 query 细节** → 要求 Planner 的步骤用途保留执行所需关键目标，并用纯 query 无 SOP 测试验证。
- **query 与告警描述冲突** → 规格明确 query 定义诊断目标、告警补充上下文；报告阶段仍以真实证据判断可信度。

## Migration Plan

无数据库或 API 迁移。回滚时移除 Planner 的 query 参数和提示词语义即可，不影响已持久化任务。

## Open Questions

（无）
