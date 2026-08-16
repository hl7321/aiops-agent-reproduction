## Why

P11 已能把 owner-scoped 文档稳定写入 Milvus，但 Agent 尚无可调用的最终检索能力。现在需要一次性建立向量、BM25L、RRF 与真实 Qwen rerank 的完整流水线，避免后续经历仅向量检索、BM25Okapi 或伪分数等过渡方案。

## What Changes

- 新增只供 Agent 自主调用的 `knowledge_retrieval` LangChain Tool；不增加独立搜索产品 API。
- 固定 owner/tenant 后并行执行 query embedding + Milvus 向量召回，以及当前 tenant SQLite 文档语料的内存 BM25L 召回。
- 新增兼顾中文单字/bigram 与 ASCII 运维词项的确定性 tokenizer；BM25L 不相交词项得零且分数不为负。
- 使用 `RRF(k=60)` 融合两路排名，最多向真实 Qwen rerank 提交 20 个候选，最终返回不超过 5 个结果且不设置最低阈值。
- 返回完整阶段排名与分数、稳定引用字段和兼容 `score=rerankScore`；无结果不生成兜底内容，任一必需分支失败均返回安全明确错误。
- 增加 Tool 输入、输出、引用共享合同以及 tokenizer、并行、RRF、rerank、失败语义、tenant 隔离和 import-safety 测试。
- 真实 Qwen+Milvus smoke 只在 ignored 本机配置和服务可用且显式执行时运行，未执行则如实记录。

## Capabilities

### New Capabilities

- `reranked-hybrid-knowledge-retrieval`：定义 Agent knowledge retrieval Tool、双路召回、RRF、Qwen rerank、完整引用证据和安全失败行为。

### Modified Capabilities

- `api-and-sse-contracts`：增加无独立 HTTP path 的 KnowledgeRetrieval Tool input/output/citation 共享类型。

## Impact

- 后端新增 retrieval 领域模块、LangChain Tool factory、BM25L/tokenizer/RRF 纯函数和依赖注入边界，并扩展知识文档 Repository 的 owner-scoped 语料读取能力。
- 复用 P06 embedding/rerank provider、P07 Milvus adapter、P05 tenant scope 与 P11 已索引 chunk 字段；模块 import 和空结果路径不得创建外部连接。
- `packages/api-contracts` 与后端 Pydantic 合同增加 Tool DTO，但 OpenAPI path 目录不增加搜索 endpoint。
- 自动化继续使用临时 SQLite、fake embedding/vector/rerank；不依赖开发者真实凭据或服务。
