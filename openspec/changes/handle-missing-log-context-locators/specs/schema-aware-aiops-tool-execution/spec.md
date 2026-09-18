## MODIFIED Requirements

### Requirement: 工具纠错与重试有界且可审计
每个计划步骤 SHALL 最多执行三次 attempt。Pydantic validation 只负责产生结构化字段错误，独立错误策略 MUST 决定 retry、replan 或 permanent failure。可修正输入错误 MAY 将脱敏字段错误和允许 Schema 交给模型修正非权威参数；空结果 MAY 由 Replanner 调整查询；timeout、429 和临时 5xx SHALL 有界退避；配置缺失、401/403、owner 越权、工具未允许、runtime Schema 不兼容和其他永久 4xx MUST NOT 重试。Region、TopicId 以及已验证的跨步参数不得由纠错模型修改。每次 attempt MUST 写入 owner-scoped step、tool audit、持久事件和 checkpoint。失败分类 MUST 在脱敏前提下保留一段有界长度的服务端消息摘要，使失败原因可从 step、tool audit 与持久事件中读出；该摘要 MUST NOT 包含凭据、Region、TopicId 或其他敏感参数值。当失败原因是"数据本身不满足前置条件"（例如本轮没有任何带定位字段的 SearchLog 命中，导致无法构造上下文查询）时，系统 MUST NOT 重试该步骤，也 MUST NOT 把该错误交给模型修正参数；该情况 SHALL 按换计划处理，使 Replanner 能依据已有证据决定结论范围，并在失败信息中明确写出缺少的前置条件。

#### Scenario: 第二次修正成功
- **WHEN** 首次参数校验失败，模型依据脱敏错误修正 Query 或可选范围且第二次通过
- **THEN** 系统记录一次 failed attempt 和一次 succeeded attempt，并只把真实成功输出保存为证据

#### Scenario: 三次仍失败
- **WHEN** 同一步达到三次上限仍未通过校验或真实调用
- **THEN** 步骤明确失败，Replanner 只能选择其他已登记真实证据；最终证据仍不足时不得进入可信报告或案例沉淀

#### Scenario: 永久错误不重试
- **WHEN** 工具失败原因是本地配置缺失、授权拒绝、owner 越权或 Schema 版本不兼容
- **THEN** 系统只记录一次 failed attempt 并立即进入安全失败处理，不把错误交给模型猜测修复

#### Scenario: 服务端返回可读错误
- **WHEN** 外部日志服务以执行错误形式返回语法错误、字段不存在或权限不足
- **THEN** step、tool audit 与持久事件中可见该错误的脱敏摘要，且不出现凭据、Region、TopicId 的具体值

#### Scenario: 缺少日志上下文定位字段
- **WHEN** 计划需要日志前后文，但本轮 SearchLog 命中里没有任何可用的定位字段
- **THEN** 系统只记录一次失败、不进入参数纠错重试，并在失败信息里明确说明缺少定位字段；已有证据仍然有效，由 Replanner 决定结论范围
