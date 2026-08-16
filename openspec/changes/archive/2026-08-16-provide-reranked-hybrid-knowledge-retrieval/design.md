## Context

参见 [proposal.md](./proposal.md)。P10/P11 在 SQLite 保存 owner-scoped 文档正文与切分配置，并用稳定 chunk 写入 Milvus；P06 提供保序 embedding 与真实 Qwen rerank；P07 只允许 tenantId + allowedKnowledgeBaseIds 的 Milvus filter；P05 禁止模型扩大 owner scope。当前没有 Agent 可调用的检索 Tool，也没有 SQLite chunk 表，因此 BM25L 语料必须从当前 owner 的活动、索引成功文档按保存配置即时切分。

## Goals / Non-Goals

**Goals:**

- 直接实现 BM25L + Milvus + RRF + Qwen rerank 的最终检索形态，并让每个阶段可测试、可追溯。
- Tool 工厂捕获 CurrentUser/OwnerScope 与可注入依赖，模型输入只表达 query 和资源过滤。
- 两路使用相同稳定 chunkId 合并，返回适合后续 Agent reference.source 事件复用的完整 citation。
- 所有 provider 和 Milvus client 保持显式、lazy 生命周期，错误跨 Tool 边界前脱敏。

**Non-Goals:**

- 不新增搜索 HTTP endpoint、检索 UI、聊天 Agent 编排、SSE 引用发送或持久化 BM25 索引。
- 不新增 chunk SQLite 表，不把 Milvus 当全文事实来源，不实现 minimum score、自动 query rewrite 或 fallback 算法。
- 不实现多知识库管理；过滤合同为后续扩展保留数组形状，但当前只能收窄当前 owner 的默认知识库。

## Decisions

### 1. Tool 由 owner-bound factory 创建，owner/tenant 不进入模型 schema

`create_knowledge_retrieval_tool(current_user, service)` 返回 LangChain `StructuredTool`，输入 Pydantic schema 只含 query/topK/knowledgeBaseIds/documentIds。service 首先验证输入，再通过 owner-scoped Repository 求出允许 KB/文档交集。空授权集合直接返回空结果且不初始化 Milvus。

不选择全局 Tool 或让模型传 owner：全局隐式 tenant 难以审计，模型提供 owner 会形成直接越权入口。

### 2. BM25L 语料从 SQLite 权威文档即时构建，并复用 P10/P11 chunk 身份

Repository 新增首参为 `owner_user_id` 的 retrieval corpus 查询，在单条 owner-scoped SQL 中限制未删除且 `index_status=succeeded` 的文档，并按可选 KB/document 交集收窄。服务使用 P10 `chunk_document_text` 和从 P11 抽出的共享 `stable_chunk_id(documentId,index,content)` 构建不可变 corpus record。使用 `rank_bm25.BM25L`，不维护第二份持久索引。

备选是把 Milvus 返回内容作为 BM25 语料，但它只能覆盖向量粗召回集合，无法形成独立关键词分支；新增 SQLite chunk 表又超出本 change 且引入双写迁移。

### 3. tokenizer 以 Unicode 分段，中文单字/bigram 与 ASCII token 并存

tokenizer 先 NFKC + casefold，再按中文连续段和 `[a-z0-9_.$-]+` ASCII 段扫描。中文段按原顺序输出所有单字及相邻 bigram；ASCII 段整体输出，确保 `NullPointerException`、`trace_id`、`service-name`、IP/版本片段和数字不会被拆碎。空 token 文档保留空列表；对 BM25L 原始分数执行有限数校验并以 `max(0, score)` 保证非负，不相交 query 显式归零。

不选择通用中文分词器：会增加模型/字典依赖和不可控版本行为；不选择 BM25Okapi，因为小语料 IDF 可为负且违反权威算法。

### 4. 一个 gather 阶段并行运行完整向量分支与 BM25L 分支

向量 coroutine 内执行 query embedding、显式 Milvus initialize、tenant+KB search 和 owner-scoped document 后过滤；BM25 coroutine 构建当前语料并评分。二者通过 `asyncio.gather(return_exceptions=True)` 同时启动并等待两路收束。任何分支异常都转为统一 `KnowledgeRetrievalError`，不得返回另一分支的部分成功。

Milvus 粗召回 limit 固定最多 20；document filter 不进入 expression，符合 P05/P07。BM25L 同样最多保留确定性前 20；这足以形成不超过 40 个 union，再由 RRF 截到 rerank 20。

### 5. RRF 只融合 rank，tie 由 chunkId 固定

每一路先按 score 降序、chunkId 升序形成 1-based rank。union 以 chunkId 合并，`rrfScore=sum(1/(60+rank))`；按 `(-rrfScore, chunkId)` 排序后截取 20。候选 record 分别保存 vectorRank/vectorScore 和 bm25Rank/bm25Score，缺失分支保持 None。

不使用原始分数加权：COSINE 与 BM25L 不同尺度，权重需要额外调参并降低可解释性。

### 6. rerank index 映射回 RRF 候选，不覆盖历史排名

Qwen provider 接收 RRF 候选 excerpt，`top_n=min(topK,len(candidates),5)`。严格校验返回 index 唯一且在范围内、score 有限；按 provider 顺序赋 rerankRank。最终 citation 保留所有召回和融合字段，并设置 `score=rerankScore`。provider 少返回合法结果时如实返回较少结果，不设阈值也不补齐。

不使用 rerank fallback：provider 失败属于必需分支失败，伪分数会破坏合同和可观测性。

### 7. 错误按阶段分类并统一脱敏

query/topK 使用 Pydantic/领域验证错误；embedding、vector、BM25、rerank 分别包装为稳定安全阶段错误，保留 `raise ... from error` 供服务端诊断，但对 Tool 输出只暴露脱敏消息。API key、bearer、token、password 等复用现有 redaction 规则。空结果是成功 `{results: []}`，不是错误。

## Risks / Trade-offs

- **[每次查询重建 BM25L 对大语料有 CPU/内存成本]** → 当前本地单用户模型采用 owner-scoped 成功文档并限制结果；未来以独立 change 引入可失效缓存或持久倒排索引，不改变 Tool 合同。
- **[向量粗召回 20 后再做 document filter 可能少于 topK]** → 严守 Milvus filter 安全边界并如实返回较少结果，不扩大 search expression 或生成兜底。
- **[SQLite 文档成功状态与 Milvus 短暂不一致]** → P11 retry/rebuild 负责最终收敛；任一外部分支错误使本次 Tool 整体失败。
- **[asyncio.gather 中一个分支先失败]** → 使用 `return_exceptions=True` 等待两路收束，确保无悬挂任务且不把单路结果当成功。
- **[metadata 来源不可信]** → citation 的 id/source/scope 字段取自可信 record，metadata 以 adapter 已保护字段为准且不得覆盖顶层事实字段。

## Migration Plan

1. 先增加共享 contracts、纯 tokenizer/BM25L/RRF 测试和 owner-scoped corpus Repository。
2. 增加 retrieval service 与 fake 依赖流水线测试，再组装 LangChain Tool factory；不在现有 app 启动时自动联网。
3. 运行 backend/contracts/frontend contract 门禁；有真实 ignored 配置和服务时人工 smoke。
4. 回滚只移除 Tool/retrieval 模块与合同类型；不涉及 schema migration、文档或向量数据变更。
