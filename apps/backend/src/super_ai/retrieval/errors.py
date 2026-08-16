from typing import Literal, TypeAlias

RetrievalStage: TypeAlias = Literal["validation", "embedding", "vector", "bm25", "rerank"]


class KnowledgeRetrievalError(RuntimeError):
    def __init__(self, stage: RetrievalStage, message: str) -> None:
        self.stage = stage
        super().__init__(f"knowledge_retrieval {stage} 失败: {message}")
