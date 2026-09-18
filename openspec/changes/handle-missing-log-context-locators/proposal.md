# 明确处理缺失的日志定位字段

## Why

需要日志前后文的诊断步骤会反复失败并给出看不懂的原因，而真正的原因是一个**数据侧限制**：当前日志来源没有定位字段。

`DescribeLogContext` 的必填参数是 `Time`、`PkgId`、`PkgLogId`，它们只能来自本轮已验证的 `SearchLog` 原始命中。实测表明，用官方 Python SDK 的 `put_log_raw`（打到 `/structuredlog`）上传的合成日志，检索结果里 `PkgId` 与 `PkgLogId` **恒为空字符串**：

- 结构化键值内容与 `__CONTENT__` 纯文本内容都试过，都是空；
- 日志主题是标准存储（hot，保留 30 天），不是存储类型导致的；
- SDK 最新版 1.0.9 的上传路径与固定的 1.0.4 **完全相同**，protobuf 里也不存在 PkgId 字段；
- 账号内只有一个日志主题，没有可对照样本。

于是 `hit.has_context_locator` 恒为假，`DescribeLogContext` 永远拿不到必填输入。当前实现把它当作可修正的输入错误处理：重试三次、还试图让模型修改参数，最后在 step 上留下一句 `input_validation: ValueError: DescribeLogContext 缺少已验证 SearchLog 定位命中`。

**重试与模型纠错在这里都没有意义**——数据里就是没有这两个字段。结果是：浪费三次尝试、写三条无意义失败记录，而真正的限制（"这份日志源无法做上下文查询"）在系统里看不见。

## What Changes

- 把"缺少日志上下文定位字段"识别为**数据不满足前置条件**的独立失败，而不是可修正的输入错误：不再重试同一个步骤，也不再交给模型修改参数。
- 该失败按"换计划"处理：已有 `log_hit` 证据仍然有效，Replanner 据此判断结论范围，必要时产出证据不足的诚实报告，而不是让整次诊断失败。
- 失败信息明确指出原因（缺少日志定位字段，无法获取上下文），使该限制在 step、tool audit 与持久事件里直接可读。
- 运行手册与已知限制文档记录该结论与已验证的排查过程。

非目标：

- 不改用其它上传路径去强行产出 `PkgId`：官方 SDK 没有可用替代入口，控制台采集路径不在本仓库可控范围内。
- 不改 `DescribeLogContext` 的必填参数定义，也不放宽定位字段校验。
- 不改 attempt 上限、退避策略与其它失败分类。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: 缺少日志上下文定位字段必须按数据前置条件不足处理，不做无意义重试；该限制必须可读且被文档化。

## Impact

- 影响的模块：`apps/backend/src/super_ai/aiops`（`tool_failures` 的分类映射、`runtime` 的上下文步骤前置检查）。
- 影响的接口：无 HTTP/SSE 形状变更；`DescribeLogContext` 失败时的 step 记录与事件内容更明确。
- 文档：`docs/runbooks/`、`openspec/specs/` 相关说明。
- 依赖：无新增依赖。
- 风险：低。仅改变失败分类与提示文本，不改变成功路径。
