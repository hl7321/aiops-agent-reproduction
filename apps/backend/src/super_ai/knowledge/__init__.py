"""知识文档领域；导入不会读取配置、数据库或连接 Milvus。"""

from super_ai.knowledge.chunking import ChunkingConfig, chunk_document_text

__all__ = ["ChunkingConfig", "chunk_document_text"]
