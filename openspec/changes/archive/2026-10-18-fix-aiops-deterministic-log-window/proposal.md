# 让诊断日志时间窗确定化，并让演示日志一次上传可反复验证

## Why

同一个告警、同一批日志，诊断能不能查到数据，目前取决于**模型这一次怎么算时间窗**。2026-10-16 的抓包记录了四种不同写法：

- `[告警时刻 − 15 分钟, 告警时刻]`
- `[告警时刻, 告警时刻 + 15 分钟]`
- `[告警结束时间 − 15 分钟, 告警结束时间]`
- 一个取整后的 3 小时区间

结果就是：任务 `197c4df6` 一次命中，任务 `acba86e0` 第一次查询为空、靠重试才命中。时间窗是**可计算的事实**，不该让模型每次现编。

第二个问题是演示数据的时间方向。`java-ecommerce` fixture 把十套场景的日志时间写成**上传时刻 + 0~9 分钟**，而告警紧接着上传发布（`startsAt = 发布时刻`）。因此当模型采用"从告警往回 15 分钟"的窗口时，只有第一套场景落在窗口里，其余九套都在窗口外。

实测确认：

- CLS 主题的保留期是 **30 天**（`Period = 30`），不是永久；
- 本次上传后 **约 1 分钟**即可检索到，之前的 10~18 分钟延迟没有复现。
- **告警本身只有 2 小时有效期**：发布脚本固定写 `endsAt = startsAt + 2 小时`，过期后前端就看不到活跃告警，也无法再发起诊断。

所以"日志传一次、随时验证"的目标本身成立，缺的是**把时间窗固定下来、并让日志时间落在告警窗口内**。

## What Changes

**1. 时间窗改为服务端确定性注入。**

- `SearchLog` 的 `From`/`To` 不再由模型生成，也不再出现在模型可见的参数说明中。
- 服务端按告警时间与配置计算窗口：`[最早 startsAt − before, 最晚 startsAt + after]`；单条告警即退化为 `[startsAt − before, startsAt + after]`。
- 新增配置 `clsLogUpload.windowBeforeMinutes`（默认 15）与 `windowAfterMinutes`（默认 0），同步基础模板与用户模板。
- 告警缺少可解析的 `startsAt` 时，诊断在调用 SearchLog 前以明确错误失败，不猜测时间。

**2. 演示日志的时间方向改到告警之前。**

- 十套 `java-ecommerce` fixture 的日志时间改为在上传时刻之前的 9 分钟内依次排开（`T−9 ~ T`），保持每套场景内部四段日志的有序性与关联字段不变。
- 这样"上传日志 → 立刻发布告警 → 等待入库 → 诊断"就能自然落在 `[告警时刻 − 15 分钟, 告警时刻]` 内。

**3. 告警脚本支持显式对齐时间。**

- `publish_java_ecommerce_alerts.py` 新增 `--starts-at <ISO 8601>`，用于重放或对齐已有日志；不带该参数时保持 `startsAt = 当前时间`。
- `endsAt` 仍为 `startsAt + 2 小时`；时间必须带时区，拒绝裸时间。

**4. 文档修正。**

- README 把"日志长期保留"更正为"当前主题保留 30 天"，并写明演示准备顺序。
- `correlated-ecommerce-aiops-fixtures` 规格中"SearchLog 必返回非空 PkgId/PkgLogId"的旧表述与现状不符：当前上传链路恒返回空串，`DescribeLogContext` 因此不可用。该表述随本次规格修订一并修正，不改变工具可用性。

**5. 演示告警支持 30 天有效期。**

- `publish_java_ecommerce_alerts.py` 新增 `--active-days`（默认不填仍为 2 小时）；演示时传 `--active-days 30`，`endsAt = startsAt + 30 天`。
- 新增 `--ensure`：先查 Alertmanager，已有 10 条活跃告警就跳过发布，避免重复写入。
- 说明：Alertmanager 的告警状态不跨容器重启持久化；容器重启后需要再执行一次 ensure 命令。应用不会在启动时自动发布外部告警。

非目标：

- 不解决 `PkgId`/`PkgLogId` 的产生方式，也不恢复 `DescribeLogContext`。
- 不调整诊断上下文瘦身、模型选择、报告 claim 契约。
- 不改变 CLS 的 30 天保留策略本身。
- 不在应用启动时自动发布告警；告警补齐由显式脚本命令完成。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `schema-aware-aiops-tool-execution`: 时间窗从"执行者判断字段"改为"服务端确定性注入"，`From`/`To` 不再对模型可见。
- `correlated-ecommerce-aiops-fixtures`: 日志时间改为上传时刻之前的 0~9 分钟；告警发布脚本支持 `--starts-at`、`--active-days` 与 `--ensure`；修正 PkgId 相关的过期表述。

## Impact

**后端**

| 文件 | 影响 |
|---|---|
| `apps/backend/src/super_ai/alerts/settings.py` | `clsLogUpload` 新增窗口偏移字段（带默认值，兼容旧配置） |
| `apps/backend/src/super_ai/aiops/factory.py` | 把窗口配置传给 `SearchLogQueryDefaults` |
| `apps/backend/src/super_ai/aiops/planning.py` | `SearchLogQueryDefaults` 增加窗口字段；SearchLog 参数装配注入 From/To |
| `apps/backend/src/super_ai/aiops/runtime.py` | 从告警 `startsAt` 计算窗口并传入参数装配；告警时间不可解析时明确失败 |
| `apps/backend/src/super_ai/aiops/tool_policy.py` | SearchLog 的 `From`/`To` 加入服务端注入字段，不再出现在模型可见 schema |

**脚本与配置**

- `scripts/java_ecommerce_aiops_fixtures.py`：日志时间改为 `T−9 ~ T`。
- `scripts/publish_java_ecommerce_alerts.py`：新增 `--starts-at`、`--active-days`、`--ensure`。
- `config/project.template.json`、`config/user.project.template.json`：新增两个窗口字段。

**文档**：README 与相关教程补充 30 天保留期和演示准备顺序。

**测试**：

- SearchLog 参数装配不再接受模型给的 From/To，按告警时间与配置注入；
- 多告警取最早/最晚时间，缺 `startsAt` 时明确失败；
- 模型可见 schema 不含 From/To；
- fixture 时间戳落在生成时刻之前的 9 分钟内且顺序稳定；
- `--starts-at` 解析、时区校验与 `endsAt` 计算；
- `--active-days 30` 产生 30 天有效期，`--ensure` 在已有告警时跳过发布；
- 真实 smoke：同一批日志、只发一次告警，连续两次诊断都能命中。
