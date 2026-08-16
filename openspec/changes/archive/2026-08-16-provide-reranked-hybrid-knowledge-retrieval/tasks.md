## 1. 共享合同与纯算法

- [x] 1.1 先编写 KnowledgeRetrieval Tool input/output/citation、可空阶段 rank/score、无 owner/tenant 输入和无新增 OpenAPI path 的合同失败测试
- [x] 1.2 实现 TypeScript/Pydantic Tool 合同与导出，并保持 `score=rerankScore` 的序列化约定
- [x] 1.3 先编写中文单字/bigram、ASCII 运维 token、NFKC/casefold、小语料正 IDF、不相交零分和无 BM25Okapi 的失败测试
- [x] 1.4 实现 tokenizer 与 `rank_bm25.BM25L` scorer，拒绝非有限结果并保证 BM25 分数非负
- [x] 1.5 先编写 RRF `k=60` 公式、单路 null、稳定 chunkId tie 和最多 20 候选失败测试，再实现不可变候选融合

## 2. Owner-scoped 语料与检索流水线

- [x] 2.1 抽取 P11 共用稳定 chunkId，并先编写 preview/index/retrieval 对同一 chunk 身份的回归测试
- [x] 2.2 先编写 Repository 首参 owner、只读活动且 succeeded 文档、KB/document 交集和跨 owner 不可见测试，再实现 retrieval corpus 查询
- [x] 2.3 先编写 query/topK 校验、默认 5、授权过滤交集、空授权集合不连接外部服务的失败测试
- [x] 2.4 先编写向量分支与 BM25L 分支并行启动、Milvus filter 仅 tenant+KB、document 后过滤和单路未命中测试
- [x] 2.5 实现可注入 retrieval service：并行两路、RRF 截断、真实 rerank 映射、最终 topK 和完整 citation
- [x] 2.6 先编写 rerank 改序仍保留原始排名、低分无阈值、少量返回不补齐、空结果不 rerank/不兜底测试
- [x] 2.7 先编写 embedding/vector/BM25/rerank 分阶段失败、脱敏、无单路降级和无假分数测试，再实现稳定错误边界

## 3. LangChain Tool 与安全治理

- [x] 3.1 先编写 `knowledge_retrieval` StructuredTool 名称/schema、owner-bound factory 和模型不能传 owner/tenant 的失败测试
- [x] 3.2 实现 LangChain Tool factory 与显式依赖组装，不新增搜索 HTTP endpoint 或 import-time client
- [x] 3.3 增加跨租户外部调用短路、Repository 参数治理、BM25Okapi/create_task/私有合同禁用和 import-safety 测试
- [x] 3.4 更新后端 README 与真实 Qwen+Milvus smoke runbook；无有效 ignored JSON 或服务不可用时明确记录未执行

## 4. 验证与归档

- [x] 4.1 运行 backend Ruff、strict Pyright、全量 pytest 与无需 migration 的 schema 回归
- [x] 4.2 运行 contracts typecheck/test、相关 frontend typecheck/test/build、`openspec validate --all` 和 `git diff --check`
- [x] 4.3 使用 openspec-verify-change 核对全部任务、requirements、scenarios 与 design，修复所有 CRITICAL/WARNING
- [x] 4.4 同步两个 delta specs、归档 change，并复检无 active change 与最终格式门禁
