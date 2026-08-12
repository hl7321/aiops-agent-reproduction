"""知识文档删除端口到 tenant-safe Milvus adapter 的桥接。"""

from super_ai.tenancy.context import OwnerScope
from super_ai.tenancy.vector_scope import VectorScope
from super_ai.vector_store.adapter import MilvusVectorStore


class MilvusDocumentVectorDeleter:
    def __init__(self, vector_store: MilvusVectorStore) -> None:
        self._vector_store = vector_store

    async def delete_document(
        self, scope: OwnerScope, knowledge_base_id: str, document_id: str
    ) -> None:
        vector_scope = VectorScope(
            tenant_id=scope.tenant_id,
            owner_user_id=scope.owner_user_id,
            allowed_knowledge_base_ids=(knowledge_base_id,),
        )
        await self._vector_store.delete_document(vector_scope, knowledge_base_id, document_id)
