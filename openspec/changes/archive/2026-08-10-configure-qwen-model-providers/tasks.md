## 1. 配置加载器与最终模板

- [x] 1.1 先为缺失文件、非法 JSON、非 object 顶层和不回显配置内容编写失败测试
- [x] 1.2 实现稳定 `ProjectConfigError` 并保持显式路径深合并与无环境变量读取
- [x] 1.3 先为最终 section、空 credential、本机配置 ignored 和前端新增 secret allowlist 编写失败策略测试
- [x] 1.4 扩展两份模板和 ignored 本机配置，使策略测试与前端 secret 扫描通过

## 2. Typed LLM 配置

- [x] 2.1 先为 nested override、缺失字段、URL/数值、capability profile 和环境变量隔离编写失败测试
- [x] 2.2 实现 frozen Pydantic v2 LLM/model capability settings、安全 validation error 与显式 JSON settings loader
- [x] 2.3 验证模板默认 chat/embedding/rerank 参数和空 API key 的 factory 前拒绝语义

## 3. Chat 与 Embedding provider

- [x] 3.1 先为 `LlmProvider` 参数、ChatOpenAI factory 和 capability profile 编写失败测试
- [x] 3.2 实现 `QwenOpenAIProvider.create_chat_model`，只在显式 factory 路径创建 ChatOpenAI
- [x] 3.3 先为 OpenAIEmbeddings 参数、23 条 10/10/3 分批、原文/顺序和空输入短路编写失败测试
- [x] 3.4 实现 embedding factory 与顺序分批，拒绝向量数量不匹配且不创建 fallback

## 4. Rerank 与 Readiness

- [x] 4.1 先为 qwen3-vl-rerank payload、真实 index/score、空输入、timeout retry 和错误耗尽编写失败测试
- [x] 4.2 实现独立可注入 HTTP rerank client、最多 2 次 retry、响应校验和无 fallback 结果
- [x] 4.3 先为三类最小异步 readiness、latency 元数据和 API key 多次脱敏编写失败测试
- [x] 4.4 实现 readiness 与统一 `ModelProviderError` 脱敏出口

## 5. 导入安全、依赖与文档

- [x] 5.1 增加 import-safety 与无 DashScope SDK 依赖测试，证明导入不读配置、不创建 client、不联网
- [x] 5.2 运行 `uv sync` 并验证锁文件只使用既定 langchain-openai/httpx 边界
- [x] 5.3 更新 AGENTS、后端 README、架构文档与真实凭据人工 smoke 指南，明确 smoke 未执行

## 6. 验证与归档准备

- [x] 6.1 运行并修复 backend Ruff、strict Pyright、pytest 和 contracts 相关门禁
- [x] 6.2 运行前端 public-config/secret 回归、`openspec validate --all` 与 `git diff --check`
- [x] 6.3 执行 `$openspec-verify-change`，修复全部 CRITICAL/WARNING 并确认 delta specs 可同步归档
