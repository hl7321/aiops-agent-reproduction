# 支持 chat 模型使用独立端点与密钥

## Why

当前 `llm` 只有一份 `baseUrl` 和一份 `apiKey`，chat、embedding、rerank 三类能力必须共用同一个
OpenAI-compatible 端点和凭据。用户想把 chat 换成 DeepSeek（`deepseek-chat`）来降低成本与延迟，
但 embedding 和 rerank 仍要留在百炼——DeepSeek 并不提供 embedding 服务，所以现在这套配置
根本无法表达"chat 走 A、embedding/rerank 走 B"。

## What Changes

- `llm.chat` 新增两个**可选**字段：`baseUrl` 与 `apiKey`。
  - 未配置或为空字符串时，沿用 `llm.baseUrl` / `llm.apiKey`（保持既有单端点行为）。
  - 配置后只影响 chat；embedding 与 rerank 继续使用 `llm.baseUrl` / `llm.apiKey`。
- `llm.provider` 从枚举 `qwen-openai` 改为**非空字符串标签**（默认仍是 `qwen-openai`），
  因为它描述的是这份配置的部署形态，不是每个能力各自的厂商。
- chat 的凭据使用**生效值**参与脱敏：chat 请求失败时替换的是 chat 真正使用的 key，
  不允许把 chat 密钥在错误信息里漏出去。
- `readiness("chat")` 返回 chat 的**生效** base URL（不再固定返回 `llm.baseUrl`）。
- chat 模型仍必须在 `modelCapabilities` 登记 `contextWindowTokens`；缺失时的报错文案改成可操作的提示。
- 本地 `config/project.json` 把 chat 切到 DeepSeek，embedding/rerank 保持百炼；模板同步新增字段形状。

**非目标**：不重命名 `QwenOpenAIProvider`、不重命名 `/ready` 的 `qwen` 依赖键、不做自动 fallback、
不做模型路由、不改 embedding 与 rerank 的模型与参数。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `qwen-model-providers`：模型配置新增 chat 级端点与凭据覆盖；`provider` 由枚举放宽为非空标签；
  readiness 的 chat 分支返回生效 base URL；脱敏按能力使用生效凭据。

## Impact

- 配置：`config/project.template.json`、`config/user.project.template.json`、本地 `config/project.json`
  与 `config/user.project.json`。
- 代码：`apps/backend/src/super_ai/llm/config.py`（字段与生效值）、
  `apps/backend/src/super_ai/llm/provider.py`（chat 分支）、`docs/architecture/model-providers.md`。
- 测试：`apps/backend/tests/llm/*`（配置、provider、readiness、embedding 不受影响的回归）。
- 兼容性：既有只填 `llm.apiKey` 的本地配置无需改动即可继续跑；本次不是 BREAKING。
