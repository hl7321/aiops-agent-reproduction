## Context

当前 `LlmSection` 只有一份 `baseUrl` 与一份 `apiKey`，`ChatSettings` 只带 `model/temperature/timeout/maxRetries`。
三种能力（chat、embedding、rerank）在 provider 里各自创建 client，但都从 `LlmSettings.base_url` 和
`require_api_key()` 取端点与凭据；`modelCapabilities` 是 chat 模型名到 `contextWindowTokens` 的登记表，
`capability_for_chat()` 在缺少登记时直接失败。

动机见 `proposal.md`——这里只说明怎么做，以及为什么不选其他做法。

## Goals / Non-Goals

**Goals:**

- 用最小配置表达"chat 走一家厂商、embedding/rerank 走另一家"。
- 保持既有只填 `llm.apiKey` 的本地配置零改动可用。
- 脱敏按"这次调用真正用的那把 key"生效，不因为引入第二把 key 而留下泄露口子。
- 换模型时如果漏登记 capability，报错要直接说清楚该补哪一项。

**Non-Goals:**

- 不改 `QwenOpenAIProvider` 类名、不改 `/ready` 的 `qwen` 依赖键（属于契约重命名，另开变更）。
- 不做自动 fallback、不做按请求路由、不做多套 provider 并存。
- 不给 embedding/rerank 增加独立端点覆盖——本轮没有这个需求，加了反而要维护三套生效值。

## Decisions

### 1. 覆盖字段放在 `llm.chat` 下面，而不是新增 `llm.chatProvider`

`chat.baseUrl` / `chat.apiKey` 与被覆盖的对象处在同一层，配置读起来是"chat 用这个端点"，
也不用在顶层再引入一个和 `llm` 平行的结构。

被否方案：在 `llm` 下新增 `capabilities: { chat: {...}, embedding: {...} }` 的完全对称结构。
它更整齐，但会**移动**现有 embedding/rerank 字段，属于破坏性配置变更，收益不抵迁移成本。

### 2. 空字符串等于"未提供"

模板必须是可提交的，所以覆盖字段在模板里是空串。校验器先把空串归一成 `None`，
再对非空值做 http/https 校验。这样"模板里的空值"和"用户没写这个字段"行为一致，
不会出现"模板复制下来就校验失败"。

### 3. `provider` 放宽为非空字符串标签

这个字段唯一的用途是被写进 readiness 结果，而 readiness 结果不参与任何用户可见契约
（`/ready` 只取 `status/latency/error`）。既然一份配置现在可能跨两家厂商，
写死枚举只会逼用户填一个不真实的标签。默认值仍是 `qwen-openai`，老配置不受影响。

被否方案：保留枚举并新增 `deepseek-openai`、`openai-compatible` 等取值。
每接一家厂商就要改一次代码和规格，收益为零。

### 4. 生效值在 settings 上收敛成显式方法

`chat_base_url()` / `chat_api_key()`（以及 embedding/rerank 继续用 `base_url` / `require_api_key()`）
把"取哪把钥匙"的判断收在一处，provider 里不再各写一遍 `or` 逻辑。
chat 分支的 client 参数、readiness 返回值和异常脱敏**都从同一个方法取值**，
避免出现"client 用了 chat key、脱敏还在用顶层 key"这种半截改动。

### 5. 脱敏绑能力，不绑全局

`sanitize_exception(error, key)` 的第二个参数改成该能力的生效 key：
chat 用 chat key，embedding/rerank 用顶层 key。另外，如果两把 key 同时存在，
chat 分支在脱敏时把两把都替换掉——多脱一层不会误伤，漏脱一层就是事故。

### 6. capability 登记保持强约束，只改报错文案

`contextWindowTokens` 影响聊天记忆压缩阈值，猜一个默认值会让压缩时机错得没有痕迹。
所以仍然要求显式登记，但错误里带上"需要在 `modelCapabilities` 补一条同名条目"的指引。

## Risks / Trade-offs

- [风险] DeepSeek 的模型 id 与上下文窗口随版本变化，写进模板的数字可能过时
  → 模板保留百炼默认值不动，只在本机 `config/project.json` 里切到 DeepSeek；
  文档写明"`contextWindowTokens` 必须按实际模型填，填小了只是提前压缩，填大了才有截断风险"。
- [风险] 同一进程里两把 key，日志/错误里可能出现另一把
  → chat 分支脱敏时同时替换两把 key，并用单测锁住"独立密钥不出现在错误里"。
- [代价] `provider` 放宽后，配置里可以写任意标签，失去一种拼写校验
  → 该字段不影响任何运行分支，只影响 readiness 展示，风险可接受。

## Migration Plan

1. 先合并代码与模板（模板里的 chat 覆盖字段为空，行为与现在完全一致）。
2. 本机 `config/project.json` 把 chat 切到 DeepSeek，并在 `modelCapabilities` 加一条登记。
3. 本机 `config/user.project.json` 在 `llm.chat.apiKey` 填 DeepSeek 的 key，`llm.apiKey` 保持百炼 key 不动。
4. 重启后端，`/ready` 的 `qwen` 项变绿即表示 chat 生效端点可达；embedding 与知识库检索不受影响。

回滚：把 `config/project.json` 的 `llm.chat` 改回百炼模型与端点（或删除这两个覆盖字段）即可，代码无需回滚。

## Open Questions

- 是否把 `/ready` 的 `qwen` 依赖键改名为 `llm`：这是契约层重命名，涉及前端与契约测试，留待单独变更。
- DeepSeek 的 `modelCapabilities.contextWindowTokens` 取值以实际使用模型为准，本机先按保守值登记。
