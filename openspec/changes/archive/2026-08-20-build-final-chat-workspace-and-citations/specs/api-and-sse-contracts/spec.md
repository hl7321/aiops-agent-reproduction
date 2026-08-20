## ADDED Requirements

### Requirement: Chat 引用复用完整 Knowledge Retrieval citation
共享 contracts SHALL 使 ChatReference、assistant message metadata references 与 `reference.source` 使用同一完整 citation 形状：chunkId、documentId、knowledgeBaseId、source、excerpt、metadata、vectorRank/vectorScore、bm25Rank/bm25Score、rrfScore、rerankRank、rerankScore 和兼容 score。vector/BM25 未命中字段 MUST 保持 null，`score` MUST 等于 rerankScore。TypeScript、Pydantic、SSE guard 与合同测试 MUST 一致，不得保留只有 id/title 的私有引用形状。

#### Scenario: SSE 传输完整引用
- **WHEN** knowledge_retrieval 产生一条完整 citation
- **THEN** reference.source 与成功 assistant metadata 以相同字段和值传输，nullable rank/score 不被改写

#### Scenario: 合同拒绝不完整引用
- **WHEN** SSE parser 收到缺少 documentId、metadata 或 rerankScore 的 reference.source
- **THEN** 事件守卫拒绝该 payload，而不是把它当作有效引用
