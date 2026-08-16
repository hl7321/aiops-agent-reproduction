## ADDED Requirements

### Requirement: 共享合同登记 Knowledge Retrieval Tool
共享合同 SHALL 定义 KnowledgeRetrievalToolInput、KnowledgeRetrievalToolOutput 与 KnowledgeRetrievalCitation 类型。输入包含 query、可选 topK、knowledgeBaseIds 和 documentIds，但 MUST NOT 包含 ownerUserId 或 tenantId；citation 包含稳定 chunk/document/KB id、source/excerpt/metadata、vectorRank/vectorScore、bm25Rank/bm25Score、rrfScore、rerankRank/rerankScore 及兼容 score。此合同 MUST NOT 在机器可读 OpenAPI path 目录增加独立搜索 endpoint。

#### Scenario: 合同消费者创建 Tool 输入
- **WHEN** Agent 层使用共享 input 类型调用 knowledge_retrieval
- **THEN** 可表达 query、topK 和资源过滤，但不能通过合同传入 owner 或 tenant

#### Scenario: 合同消费者读取完整 citation
- **WHEN** Tool 返回双路或单路候选
- **THEN** citation 的阶段 rank/score 具有精确可空语义，且 score 与 rerankScore 均为必填数值

#### Scenario: OpenAPI 不暴露搜索产品 API
- **WHEN** 合同测试遍历机器可读 path 目录
- **THEN** 不存在为本 Tool 新增的独立 knowledge search HTTP path
