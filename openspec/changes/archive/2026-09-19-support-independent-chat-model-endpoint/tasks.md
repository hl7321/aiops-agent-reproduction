## 1. 配置 schema

- [x] 1.1 `ChatSettings` 新增可选 `baseUrl` 与 `apiKey`；空字符串归一为未提供，非空 `baseUrl` 按 http/https 且无凭据校验
- [x] 1.2 `LlmSettings` 暴露生效值：`chat_base_url()`、`chat_api_key()`；顶层 `base_url` / `require_api_key()` 行为不变
- [x] 1.3 `llm.provider` 由枚举放宽为非空字符串标签（默认仍为 `qwen-openai`）
- [x] 1.4 chat 模型缺少 `modelCapabilities` 登记时的报错补上"该补哪一项"的指引

## 2. provider 生效值与脱敏

- [x] 2.1 `create_chat_model()` 使用 chat 生效端点与生效密钥
- [x] 2.2 chat 分支脱敏改为按生效密钥，并在两把 key 同时存在时一并替换
- [x] 2.3 `readiness("chat")` 返回 chat 生效 base URL；embedding/rerank 行为不变

## 3. 配置模板与本地配置

- [x] 3.1 `config/project.template.json` 与 `config/user.project.template.json` 补上 chat 覆盖字段（空值）
- [x] 3.2 本机 `config/project.json` 把 chat 切到 DeepSeek 端点与模型，并登记 `modelCapabilities`
- [x] 3.3 确认本机 `config/user.project.json` 的 `llm.apiKey` 仍是百炼 key，新增位置留给 `llm.chat.apiKey`

## 4. 文档

- [x] 4.1 `docs/architecture/model-providers.md` 补"chat 独立端点与密钥"的配置说明与生效规则
- [x] 4.2 文档写明 `contextWindowTokens` 必须按实际模型登记，以及换模型时改哪两处

## 5. 测试与验证

- [x] 5.1 单测：chat 覆盖端点与密钥后，embedding/rerank 仍使用顶层端点与密钥
- [x] 5.2 单测：覆盖字段为空串时回退到顶层值
- [x] 5.3 单测：chat 的 `baseUrl` 非法时报错指向 `llm.chat.baseUrl`
- [x] 5.4 单测：readiness 的 chat 分支返回生效 base URL
- [x] 5.5 单测：chat 使用独立密钥时异常脱敏仍替换 `[redacted]`
- [x] 5.6 单测：`llm.provider` 接受任意非空标签，空字符串被拒绝
- [x] 5.7 回归：既有只填 `llm.apiKey` 的配置加载与 embedding 批量、rerank 重试测试保持通过
- [x] 5.8 门禁：`uv run pytest`（594 passed）、`uv run ruff check .`、`uv run pyright`、`openspec validate --all`、`git diff --check`
- [x] 5.9 真实验证（部分执行，如实记录）：用本机真实凭据跑通了 embedding readiness（`text-embedding-v4` → 百炼端点，7.8 秒），证明顶层凭据路径未受影响；**chat 的真实凭据 smoke 未执行**——DeepSeek key 尚未填入 `llm.chat.apiKey`，未执行就不声称成功
