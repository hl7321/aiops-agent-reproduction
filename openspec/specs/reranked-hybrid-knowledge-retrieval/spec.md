# reranked-hybrid-knowledge-retrieval Specification

## Purpose

本能力为 Agent 提供始终按当前用户隔离的最终知识检索 Tool，以并行向量召回和 BM25L 关键词召回、确定性 RRF 融合及真实 Qwen rerank 返回完整可追溯引用。

## Requirements

### Requirement: Agent Tool 输入受限且 tenant scope 不可扩大
系统 SHALL 提供名为 `knowledge_retrieval` 的 LangChain Tool。输入 MUST 包含非空 query，可选 topK、knowledgeBaseIds 和 documentIds；topK 默认 5、最小 1、最大 5。Tool MUST 在处理模型输入前从当前认证用户固定 ownerUserId 与 tenantId，并将模型传入的过滤条件与 owner 可见资源求交集，MUST NOT 接受或推断模型提供的 owner/tenant。

#### Scenario: 使用默认 topK
- **WHEN** Agent 以非空 query 调用 Tool 且未提供 topK
- **THEN** Tool 最多返回 5 条当前用户结果

#### Scenario: 拒绝非法输入
- **WHEN** query 为空白或 topK 超出 1 到 5
- **THEN** Tool 在调用 embedding、Milvus、BM25L 或 rerank 前返回安全验证错误

#### Scenario: 模型过滤条件不能扩大权限
- **WHEN** 模型传入其他用户的 knowledgeBaseId 或 documentId
- **THEN** 不返回跨 owner 数据，且未获授权的过滤值不能进入外部搜索 scope

### Requirement: 向量与 BM25L 两路召回并行执行
系统 SHALL 对 query 生成真实 embedding，并将 query embedding + Milvus 向量召回作为一个异步分支，与当前 owner 活动且索引成功文档语料的内存 BM25L 召回并行执行。Milvus filter MUST 只包含当前 tenantId 与 owner 允许的 knowledgeBaseIds；documentIds MUST 在 owner-scoped 粗召回后过滤。两路候选 MUST 使用同一稳定 chunkId 对齐。

#### Scenario: 双分支并行
- **WHEN** owner 有可检索文档并调用 Tool
- **THEN** 向量分支与 BM25L 分支在同一并行阶段启动，任一路等待不得阻止另一路开始

#### Scenario: 单路未命中
- **WHEN** 一个 chunk 只被向量或 BM25L 分支召回
- **THEN** 该候选仍参与融合，未命中分支的 rank 与 score 为 null

#### Scenario: document filter 后置执行
- **WHEN** 输入包含 owner 可见 documentIds
- **THEN** Milvus expression 不包含 documentId，向量粗召回结果与 BM25L 语料均在当前 owner scope 内按 documentIds 收窄

### Requirement: 中文与 ASCII tokenizer 保留运维检索语义
tokenizer SHALL 对规范化后的中文连续文本同时产生单字与相邻 bigram，并完整保留小写化的英文、数字、下划线、点号、连字符及 Java 类名、trace/service 等 ASCII 运维 token。BM25L 中 query 与文档无相交词项时分数 MUST 为 0，所有 BM25 分数 MUST 非负；小语料中的命中词 MUST 具有正 IDF 贡献。系统 MUST 使用 BM25L，MUST NOT 使用 BM25Okapi。

#### Scenario: 中文单字与 bigram
- **WHEN** tokenizer 处理“订单服务异常”
- **THEN** 结果同时包含有序中文单字与“订单”“单服”“服务”“务异”“异常”等 bigram

#### Scenario: 保留 ASCII 运维 token
- **WHEN** tokenizer 处理 Java 类名、trace_id、service-name、版本号或数字
- **THEN** 相应 ASCII token 被完整保留并按大小写无关方式匹配

#### Scenario: 小语料和不相交查询
- **WHEN** 小语料中一个文档命中 query、另一个完全不相交
- **THEN** 命中文档 BM25L 分数为正，不相交文档分数为 0，且没有负分

### Requirement: RRF 以固定公式确定性融合
系统 SHALL 按每个分支的 1-based rank 使用 `1/(60+rank)` 求和计算 RRF；未命中分支贡献 0。融合 MUST 先按 rrfScore 降序，再使用稳定 chunkId 作为最终 tie-break，结果不受 map、set 或异步完成顺序影响；送入 rerank 的候选 MUST 不超过 20。

#### Scenario: 验证 RRF 公式
- **WHEN** chunk 的 vectorRank 为 1 且 bm25Rank 为 2
- **THEN** rrfScore 精确等于 `1/61 + 1/62`

#### Scenario: 稳定处理并列
- **WHEN** 多个候选具有相同 rrfScore
- **THEN** 每次调用均按稳定 chunkId 得到相同顺序

#### Scenario: 限制 rerank 候选
- **WHEN** 融合后候选超过 20
- **THEN** 只有确定性排序前 20 条进入 rerank

### Requirement: 真实 Qwen rerank 决定最终结果
系统 SHALL 将融合候选正文和 query 交给既有真实 Qwen rerank provider，按 provider 返回的 index 与 relevance score 重排，MUST NOT 生成 fallback 分数或设置最低分阈值。最终结果数量 MUST 为 `min(topK, rerank 返回数, 5)`；rerank 后的 rank 从 1 开始，兼容 score MUST 等于 rerankScore，而 vectorRank、bm25Rank 与 rrfScore MUST 保留 rerank 前的原始值。

#### Scenario: rerank 改变顺序
- **WHEN** Qwen rerank 返回顺序与 RRF 顺序不同
- **THEN** 最终结果采用 rerank 顺序，同时每条结果保留其原始 vectorRank、bm25Rank 和 rrfScore

#### Scenario: 无最低阈值
- **WHEN** rerank 返回低但有效的 relevance score
- **THEN** 结果仍按 topK 返回且 score 等于 rerankScore

### Requirement: 结果与引用包含完整阶段证据
每条 result/citation MUST 包含稳定 chunkId、documentId、knowledgeBaseId、source、excerpt、metadata、vectorRank、vectorScore、bm25Rank、bm25Score、rrfScore、rerankRank、rerankScore 与 score。未命中分支的 rank/score MUST 为 null；excerpt MUST 来自 owner-scoped chunk 原文且不得生成或改写兜底内容。

#### Scenario: 检查双路引用
- **WHEN** 一个候选同时被两路召回并经过 rerank
- **THEN** 输出包含全部 id、引用内容、metadata、四阶段 rank/score 且 score 等于 rerankScore

#### Scenario: 检查单路引用
- **WHEN** 候选仅命中一个召回分支
- **THEN** 未命中分支的 rank 与 score 明确为 null，其余证据保持完整

### Requirement: 空结果与必需分支失败不降级
当 owner scope、过滤结果或双路召回没有候选时，Tool SHALL 返回空 results 且不得调用 rerank、生成兜底文本或虚构 citation。embedding、Milvus、BM25L 语料构建/评分或 rerank 任一必需分支失败时，Tool MUST 返回经过脱敏的明确错误，MUST NOT 静默忽略失败、改用单路结果、切换算法或伪造分数。

#### Scenario: 没有候选
- **WHEN** 两路召回均无结果或授权过滤集合为空
- **THEN** Tool 返回 `{results:[]}` 且没有 rerank 或兜底内容

#### Scenario: 各必需分支失败
- **WHEN** embedding、Milvus、BM25L 或 rerank 任一分支抛错
- **THEN** Tool 返回可识别且不泄密的失败，其他分支结果不作为成功响应返回

### Requirement: Tool 生命周期保持 lazy 且可诚实验证
导入 retrieval、tokenizer、fusion 或 Tool 模块 MUST NOT 创建模型/Milvus client、读取真实本机配置或连接网络。自动化测试 MUST 使用临时 SQLite 和 fake provider/vector adapter；真实 Qwen+Milvus smoke SHALL 仅在 ignored 本机 JSON 有有效凭据、Milvus 可用且人工显式执行时运行，未执行 MUST 明确记录。

#### Scenario: 自动化环境无真实服务
- **WHEN** 运行 import-safety 与 retrieval 自动化测试
- **THEN** 不访问网络或本机真实配置，fake 依赖仍覆盖完整流水线，并记录真实 smoke 未执行
