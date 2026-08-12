# 向量存储架构边界

## 配置与生命周期

`super_ai.vector_store.config` 只读取显式 `project.json` 和 `user.project.json` 路径，深合并后校验 `vectorStore.uri/token/collectionName`。OS 环境变量不是配置来源，浏览器也不能获得 vectorStore section。

构造 `MilvusVectorStore` 只保存 settings 和 client factory。`connect()` 才创建官方 `MilvusClient`，`initialize()` 才建立/加载 collection；health、insert、search 和 delete 需要已有连接。PyMilvus 的同步 I/O 通过线程卸载，避免阻塞 FastAPI 事件循环。当前 adapter 不声明官方不存在的 public close。

## Collection

collection 禁用 dynamic field，固定字段：chunkId、documentId、knowledgeBaseId、ownerUserId、tenantId、content、source、createdAt、metadata、vector。vector 为 1024 维 FLOAT_VECTOR，索引为 HNSW/COSINE、M=16、efConstruction=200，search ef=64；tenantId、knowledgeBaseId、documentId 使用 INVERTED 索引。

## Tenant 隔离

insert 从 `VectorScope` 生成可信 tenantId/ownerUserId 标量和 metadata，调用方 metadata 不能覆盖归属字段。search filter 只由 tenantId 与 allowedKnowledgeBaseIds 生成；空 KB 在读取 client 前返回空结果。document/metadata 条件属于未来 retrieval tool 的召回后过滤，不进入 Milvus expression。delete filter 必须同时包含 tenantId、knowledgeBaseId 和 documentId。

该 adapter 只建立持久化边界，不实现知识库、文档处理、embedding pipeline、检索工具或 RAG 产品能力。
